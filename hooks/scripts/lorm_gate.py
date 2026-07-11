#!/usr/bin/env python3
"""LORM enforcement gate — Claude Code PreToolUse/PostToolUse hook.

Usage (wired via hooks/hooks.json):
    python3 lorm_gate.py pre     # PreToolUse: authorization decision
    python3 lorm_gate.py post    # PostToolUse: audit record append

Reads the hook payload as JSON on stdin. Emits, when it has an opinion:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                            "permissionDecision": "allow|deny|ask",
                            "permissionDecisionReason": "..."}}
Exit 0 with no output = no opinion (normal Claude Code permission flow).

Design contract: docs/hard-enforcement.md in the LORM repository.
Fail posture: any internal error in `pre` degrades to "ask" with the error
in the reason (fail-closed to a human, never crash-open, never deny on our
own bug); errors in `post` never block a completed call.

Stdlib-only. PyYAML is imported lazily and only for .yaml policies; a
missing PyYAML yields "ask" with remediation advice, not a crash.
"""

import datetime
import fnmatch
import json
import os
import shlex
import sys

GATED_TOOLS = {"Bash", "Write", "Edit"}
POLICY_CANDIDATES = (
    "lorm-policy.yaml",
    "lorm-policy.json",
    os.path.join(".lorm", "policy.yaml"),
    os.path.join(".lorm", "policy.json"),
)
DEFAULT_AUDIT_LOG = os.path.join(".lorm", "audit.jsonl")
HOOK_ACTIVE_MARKER = os.path.join(".lorm", "hook-active")
SEPARATOR_TOKENS = {";", "&&", "||", "|", "&", ";;", "|&"}
REDIRECT_TOKENS = {">", ">>"}
WRAPPER_COMMANDS = {"sudo", "doas", "env", "command", "nohup", "time", "exec"}
DESTRUCTIVE_FILE_COMMANDS = {"rm", "mv", "shred", "truncate", "sed", "tee", "cp", "dd"}
RATE_WINDOW_SECONDS = 3600
SEVERITY = {"deny": 3, "ask": 2, "allow": 1}
LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")


class PolicyError(Exception):
    """Policy exists but cannot be used; maps to an 'ask' decision."""


# ---------------------------------------------------------------- utilities


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_date(value):
    """Parse a date or timestamp value from YAML/JSON; None if impossible."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        raise PolicyError("empty hook payload on stdin")
    return json.loads(raw)


def find_project_dir(payload):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return os.path.realpath(root)


def find_policy_file(project_root):
    for name in POLICY_CANDIDATES:
        candidate = os.path.join(project_root, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def load_policy(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as exc:
        raise PolicyError(f"policy file unreadable: {exc}")
    if path.endswith(".json"):
        try:
            doc = json.loads(text)
        except ValueError as exc:
            raise PolicyError(f"policy JSON parse error: {exc}")
    else:
        try:
            import yaml  # lazy: only needed for YAML policies
        except ImportError:
            raise PolicyError(
                "policy is YAML but PyYAML is not installed — "
                "run 'pip install pyyaml' or convert the policy to lorm-policy.json"
            )
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PolicyError(f"policy YAML parse error: {exc}")
    if not isinstance(doc, dict):
        raise PolicyError("policy document is not a mapping")
    return doc


def load_classifiers():
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = os.path.join(plugin_root, "hooks", "classifiers.json")
    else:
        here = os.path.dirname(os.path.realpath(__file__))
        candidate = os.path.join(here, "..", "classifiers.json")
    try:
        with open(candidate, encoding="utf-8") as fh:
            return json.load(fh).get("classifiers", [])
    except (OSError, ValueError):
        return []  # built-ins unavailable: policy matching still works


# ------------------------------------------------------- bash segmentation


def tokenize_bash(command):
    """Token list via shlex with shell punctuation; None if unparseable."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def split_segments(tokens):
    """Split a token list into command segments on shell separators."""
    segments, current = [], []
    for tok in tokens:
        if tok in SEPARATOR_TOKENS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def strip_wrappers(tokens):
    """Drop leading sudo/env/nohup/… and env-var assignments."""
    out = list(tokens)
    while out:
        head = out[0]
        if head in WRAPPER_COMMANDS:
            out = out[1:]
            # env may be followed by VAR=VAL assignments
            while out and "=" in out[0] and not out[0].startswith(("-", "/")):
                out = out[1:]
        elif "=" in head and not head.startswith(("-", "/")) and len(out) > 1:
            out = out[1:]  # bare VAR=VAL prefix
        else:
            break
    return out


def bash_match_texts(command):
    """Strings a Bash command is pattern-matched against.

    Returns (texts, segments). When the command parses, texts are the
    wrapper-stripped segments (one per shell command); the raw string is
    used only as a fallback when shlex cannot parse. Each text is evaluated
    independently: capabilities first, built-in classifiers for texts no
    capability covers — so an L5-allowed segment can never smuggle a
    dangerous sibling segment through."""
    tokens = tokenize_bash(command)
    if tokens is None:
        return [command], None
    segments = [strip_wrappers(seg) for seg in split_segments(tokens)]
    segments = [seg for seg in segments if seg]
    if not segments:
        return [command], None
    return [" ".join(seg) for seg in segments], segments


def pattern_hit(patterns, texts):
    return any(
        fnmatch.fnmatchcase(text, pat) for pat in patterns for text in texts
    )


# ------------------------------------------------------------------- paths


def norm_path(raw, cwd, project_root):
    """Return (project-relative POSIX path or None-if-outside, abs realpath)."""
    absolute = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
    real = os.path.realpath(absolute)
    rel = os.path.relpath(real, project_root)
    if rel == "." or rel.startswith(".." + os.sep) or rel == "..":
        return None, real
    return rel.replace(os.sep, "/"), real


def extract_bash_paths(segments, cwd, project_root):
    """Heuristic path candidates from bash segments (for safety nets only)."""
    found = []
    for seg in segments or []:
        for tok in seg[1:] if seg else []:
            if tok.startswith("-") or tok in REDIRECT_TOKENS:
                continue
            if "/" in tok or os.path.exists(os.path.join(cwd, tok)):
                found.append(norm_path(tok, cwd, project_root))
    return found


def glob_path(pattern, rel_path, abs_path):
    if pattern.startswith("/"):
        return fnmatch.fnmatchcase(abs_path, pattern)
    if rel_path is None:
        return False
    if fnmatch.fnmatchcase(rel_path, pattern):
        return True
    # A path that is an ancestor of the target scope is within scope:
    # acting on "build" acts on everything "build/*" covers.
    return pattern.startswith(rel_path + "/")


# ------------------------------------------------------ policy evaluation


def normalize_level(value):
    return value if value in LEVELS else None


def effective_level(cap, policy, today):
    """Return (effective level, list of degradation reasons)."""
    level = normalize_level(cap.get("level"))
    if level is None:
        return "L4", [f"capability {cap.get('id')}: invalid level declared"]
    reasons = []

    for dem in policy.get("demotions") or []:
        if isinstance(dem, dict) and dem.get("capability") == cap.get("id"):
            to = normalize_level(dem.get("to")) or "L4"
            reasons.append(
                f"active demotion to {to}: {dem.get('reason', 'no reason recorded')}"
            )
            return to, reasons

    if level != "L5":
        return level, reasons

    pol = cap.get("policy")
    if not isinstance(pol, dict):
        return "L4", ["L5 entry lacks its policy block (SPEC 8-1)"]
    expires = parse_date(pol.get("expires"))
    if expires is None:
        return "L4", ["L5 policy block has no parseable expiry (SPEC 8-2)"]
    if expires < today:
        return "L4", [f"policy expired {expires.isoformat()} (SPEC 13-1)"]
    author, approver = pol.get("author"), pol.get("approved_by")
    if not author or not approver or author == approver:
        return "L4", ["policy approver must differ from author (SPEC 8-1)"]
    return "L5", reasons


def audit_log_path(policy, project_root):
    configured = (policy.get("audit") or {}).get("log") or DEFAULT_AUDIT_LOG
    if os.path.isabs(configured):
        return configured
    return os.path.join(project_root, configured)


def is_execution_record(rec):
    return (
        isinstance(rec, dict)
        and rec.get("capability")
        and rec.get("action")
        and "x-verifies" not in rec
    )


def count_recent_executions(audit_path, capability, now):
    """Return (count, problem) — problem is a reason string if the log is
    unusable. Missing file = 0 executions (created on first append)."""
    if not os.path.exists(audit_path):
        return 0, None
    try:
        lines = open(audit_path, encoding="utf-8").read().splitlines()
    except OSError as exc:
        return 0, f"audit log unreadable: {exc}"
    count = 0
    cutoff = now - datetime.timedelta(seconds=RATE_WINDOW_SECONDS)
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            return 0, "audit log contains an unparseable line — rate limit unprovable"
        if not is_execution_record(rec) or rec.get("capability") != capability:
            continue
        ts = parse_timestamp(rec.get("timestamp"))
        if ts is None:
            return 0, "audit record with unparseable timestamp — rate limit unprovable"
        if ts > cutoff:
            count += 1
    return count, None


# ---------------------------------------------------------------- matching


def cap_matches_text(cap, tool, text):
    """Does this capability's match block cover one Bash segment text?"""
    match = cap.get("match")
    if not isinstance(match, dict):
        return False  # soft-only entry: the hook ignores it
    tools = match.get("tools")
    if tools and tool not in tools:
        return False
    patterns = match.get("command_patterns") or []
    return bool(patterns) and pattern_hit(patterns, [text])


def cap_matches_path(cap, tool, rel_path):
    match = cap.get("match")
    if not isinstance(match, dict):
        return False
    tools = match.get("tools")
    if tools and tool not in tools:
        return False
    patterns = match.get("path_patterns") or []
    return bool(patterns) and rel_path is not None and any(
        fnmatch.fnmatchcase(rel_path, pat) for pat in patterns
    )


def classifier_hit(classifiers, tool, texts, rel_path_outside):
    """First matching built-in classifier id, or None (order matters)."""
    for entry in classifiers:
        tools = entry.get("tools") or []
        if tool not in tools:
            continue
        if entry.get("path_outside_project"):
            if tool in ("Write", "Edit") and rel_path_outside:
                return entry.get("capability")
            continue
        if tool == "Bash" and pattern_hit(entry.get("command_patterns") or [], texts):
            return entry.get("capability")
    return None


# ---------------------------------------------------------- self-protection


def segment_touches(segment, *needles):
    return any(any(needle in tok for needle in needles) for tok in segment)


def self_protection(tool, tool_input, segments, cwd, project_root, policy_path, audit_path):
    """Rows P1/P2: protect the policy file (ask, SPEC I-8) and the audit
    log (deny on truncate/rewrite, append exempt, SPEC I-6)."""
    policy_real = os.path.realpath(policy_path)
    audit_real = os.path.realpath(audit_path)
    policy_base = os.path.basename(policy_real)
    audit_base = os.path.basename(audit_real)

    if tool in ("Write", "Edit"):
        raw = tool_input.get("file_path") or ""
        if not raw:
            return None
        _, real = norm_path(raw, cwd, project_root)
        if real == policy_real:
            return ("ask", "LORM I-8: policy changes require a human-reviewed "
                           "diff — the agent must not write the policy file itself")
        if real == audit_real:
            return ("deny", "LORM I-6: the audit log is append-only; "
                            "rewriting it via Write/Edit is prohibited")
        return None

    # Bash: inspect each segment that references either file
    for seg in segments or []:
        if not seg:
            continue
        joined = " ".join(seg)
        head = seg[0]
        touches_policy = policy_base in joined
        touches_audit = audit_base in joined
        if not (touches_policy or touches_audit):
            continue
        redirect_overwrite = ">" in seg
        redirect_append = ">>" in seg
        destructive = head in DESTRUCTIVE_FILE_COMMANDS
        if touches_audit:
            if redirect_append and not redirect_overwrite and not destructive:
                continue  # appending is the intended use
            if destructive or redirect_overwrite:
                return ("deny", "LORM I-6: the audit log is append-only; "
                                f"'{joined[:80]}' would rewrite or remove it")
        if touches_policy and (destructive or redirect_overwrite or redirect_append):
            return ("ask", "LORM I-8: policy changes require a human-reviewed "
                           f"diff — '{joined[:80]}' modifies the policy file")
    return None


# ---------------------------------------------------------------- decisions


def decide_for_capability(cap, policy, tool, tool_input, cap_segments,
                          cwd, project_root, audit_path, now):
    """cap_segments: only the Bash segments that matched THIS capability —
    the targets safety net must not inspect sibling segments."""
    cid = cap.get("id", "<no id>")
    level, degrade_reasons = effective_level(cap, policy, now.date())

    if level in ("L0", "L1", "L2", "L3"):
        why = degrade_reasons[0] if degrade_reasons else "listed as recommend-only"
        return ("deny", f"LORM: policy caps `{cid}` at {level} ({why}); "
                        "propose, don't execute (SPEC 2.5)")

    if level == "L4":
        why = f" ({degrade_reasons[0]})" if degrade_reasons else ""
        return ("ask", f"LORM L4: `{cid}` requires per-action human "
                       f"authorization{why}")

    # L5: remaining deterministic checks — targets and rate limit
    bounds = cap.get("bounds") or {}
    targets = bounds.get("targets") or []

    if tool in ("Write", "Edit"):
        raw = tool_input.get("file_path") or ""
        rel, real = norm_path(raw, cwd, project_root)
        if targets and not any(glob_path(p, rel, real) for p in targets):
            return ("ask", f"LORM: `{cid}` matched but {raw} is outside "
                           f"bounds.targets {targets} — degrading to L4 (SPEC 13-1)")
    else:
        path_shaped = [t for t in targets if "/" in t or t.startswith(("./", "*"))]
        if path_shaped:
            for rel, real in extract_bash_paths(cap_segments, cwd, project_root):
                if not any(glob_path(p, rel, real) for p in path_shaped):
                    return ("ask", f"LORM: `{cid}` matched but the command "
                                   f"touches paths outside bounds.targets — "
                                   f"degrading to L4 (SPEC 13-1)")

    blast = bounds.get("blast_radius") or {}
    max_per_hour = blast.get("max_actions_per_hour")
    rate_note = ""
    if isinstance(max_per_hour, int):
        count, problem = count_recent_executions(audit_path, cid, now)
        if problem:
            return ("ask", f"LORM: `{cid}` L5 entry valid but {problem} — "
                           "degrading to L4")
        if count >= max_per_hour:
            return ("ask", f"LORM: `{cid}` rate limit exhausted "
                           f"({count}/{max_per_hour} this hour) — degrading to L4")
        rate_note = f"; rate {count}/{max_per_hour} this hour"

    pol = cap.get("policy") or {}
    return ("allow",
            f"LORM: authorized by policy `{cid}` v{pol.get('version', '?')} "
            f"(expires {pol.get('expires')}){rate_note}; conditions[] remain "
            "agent-verified (soft)")


def combine(decisions):
    """Most restrictive wins: deny > ask > allow > none."""
    best = None
    for decision in decisions:
        if decision is None:
            continue
        if best is None or SEVERITY[decision[0]] > SEVERITY[best[0]]:
            best = decision
    return best


def decide_pre(payload):
    tool = payload.get("tool_name")
    if tool not in GATED_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    project_root = find_project_dir(payload)
    cwd = os.path.realpath(payload.get("cwd") or project_root)

    policy_path = find_policy_file(project_root)
    if policy_path is None:
        return None  # passive: no policy, no opinion

    policy = load_policy(policy_path)  # PolicyError handled by caller
    audit_path = audit_log_path(policy, project_root)
    now = utc_now()

    bash_texts, bash_segments = [], None
    rel_path, rel_outside = None, False
    if tool == "Bash":
        command = tool_input.get("command") or ""
        if not command.strip():
            return None
        bash_texts, bash_segments = bash_match_texts(command)
    else:
        raw = tool_input.get("file_path") or ""
        if not raw:
            return None
        rel_path, _ = norm_path(raw, cwd, project_root)
        rel_outside = rel_path is None

    decisions = [
        self_protection(tool, tool_input, bash_segments, cwd, project_root,
                        policy_path, audit_path)
    ]
    caps = [c for c in policy.get("capabilities") or [] if isinstance(c, dict)]
    classifiers = load_classifiers()

    def defaults_decision(hit):
        defaults = policy.get("defaults") or {}
        action = defaults.get("unknown_action", "escalate")
        max_level = defaults.get("max_level", "L3")
        if action == "refuse":
            return ("deny",
                    f"LORM: `{hit}`-class action is not listed in the policy "
                    f"and defaults.unknown_action is 'refuse' — the policy "
                    f"owner requires unlisted action classes to be added to "
                    f"the policy first")
        return ("ask",
                f"LORM: unlisted `{hit}`-class action "
                f"(defaults.max_level={max_level}) — approving this dialog "
                f"is the L4 human authorization (SPEC L4-1)")

    if tool == "Bash":
        # Per-segment evaluation: capabilities first; classifiers only for
        # segments no capability covers, so an allowed segment can never
        # smuggle a dangerous sibling through.
        seg_lists = bash_segments if bash_segments else [None] * len(bash_texts)
        for text, seg in zip(bash_texts, seg_lists):
            caps_here = [c for c in caps if cap_matches_text(c, tool, text)]
            for cap in caps_here:
                decisions.append(decide_for_capability(
                    cap, policy, tool, tool_input,
                    [seg] if seg else None,
                    cwd, project_root, audit_path, now))
            if not caps_here:
                hit = classifier_hit(classifiers, tool, [text], False)
                if hit:
                    decisions.append(defaults_decision(hit))
    else:
        caps_here = [c for c in caps if cap_matches_path(c, tool, rel_path)]
        for cap in caps_here:
            decisions.append(decide_for_capability(
                cap, policy, tool, tool_input, None,
                cwd, project_root, audit_path, now))
        if not caps_here:
            hit = classifier_hit(classifiers, tool, [], rel_outside)
            if hit:
                decisions.append(defaults_decision(hit))

    return combine(decisions)


# -------------------------------------------------------------------- audit


def append_audit(audit_path, record):
    os.makedirs(os.path.dirname(audit_path) or ".", exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(audit_path, "a", encoding="utf-8") as fh:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except ImportError:  # non-POSIX: best-effort append
            fh.write(line)
    marker = os.path.join(os.path.dirname(audit_path), "hook-active")
    if not os.path.exists(marker):
        open(marker, "w", encoding="utf-8").write(
            "LORM enforcement hook is active in this project.\n"
            "Soft consumers (the agent skill) must append only verification "
            "records, not execution records. See skills/lorm/references/"
            "policy-format.md.\n")


def summarize_action(tool, tool_input):
    if tool == "Bash":
        return (tool_input.get("command") or "")[:300]
    return f"{tool} {tool_input.get('file_path', '')}"[:300]


def run_post(payload):
    tool = payload.get("tool_name")
    if tool not in GATED_TOOLS:
        return
    tool_input = payload.get("tool_input") or {}
    project_root = find_project_dir(payload)
    cwd = os.path.realpath(payload.get("cwd") or project_root)
    policy_path = find_policy_file(project_root)
    if policy_path is None:
        return
    policy = load_policy(policy_path)
    audit_path = audit_log_path(policy, project_root)
    now = utc_now()

    bash_texts, bash_segments = [], None
    rel_path, rel_outside = None, False
    if tool == "Bash":
        command = tool_input.get("command") or ""
        if not command.strip():
            return
        bash_texts, bash_segments = bash_match_texts(command)
    else:
        raw = tool_input.get("file_path") or ""
        if not raw:
            return
        rel_path, _ = norm_path(raw, cwd, project_root)
        rel_outside = rel_path is None

    capability, level, authorizer = None, None, None
    caps = [c for c in policy.get("capabilities") or [] if isinstance(c, dict)]
    if tool == "Bash":
        matched = [c for c in caps
                   if any(cap_matches_text(c, tool, t) for t in bash_texts)]
    else:
        matched = [c for c in caps if cap_matches_path(c, tool, rel_path)]
    if matched:
        cap = matched[0]
        capability = cap.get("id")
        eff, _ = effective_level(cap, policy, now.date())
        # Rate limits govern the next action, not the record of this one.
        if eff == "L5":
            pol = cap.get("policy") or {}
            level = "L5"
            authorizer = f"policy:{capability}@{pol.get('version', '?')}"
        else:
            level = "L4"
            authorizer = f"human:session {payload.get('session_id', '?')}"
    else:
        hit = classifier_hit(load_classifiers(), tool, bash_texts, rel_outside)
        if hit:
            capability = hit
            level = "L4"  # it executed, so a human approved it
            authorizer = f"human:session {payload.get('session_id', '?')}"

    if capability is None:
        return  # benign call: no audit record

    output = payload.get("tool_output")
    if output is None:
        output = payload.get("tool_response")  # field name varies by CC version
    if isinstance(output, dict):
        output = (output.get("stdout") or output.get("output")
                  or json.dumps(output, ensure_ascii=False))
    if not isinstance(output, str):
        output = json.dumps(output, ensure_ascii=False) if output is not None else ""
    record = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capability": capability,
        "level": level,
        "authorizer": authorizer,
        "action": summarize_action(tool, tool_input),
        "params": {"tool": tool, "cwd": cwd},
        "diagnosis_ref": "unavailable-to-hook",
        "outcome": output[:300],
        "verified": "pending",
        "x-writer": "lorm-hook",
        "x-session": payload.get("session_id", ""),
    }
    append_audit(audit_path, record)


# --------------------------------------------------------------------- main


def emit(decision):
    if decision is None:
        return
    verdict, reason = decision
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict,
            "permissionDecisionReason": reason,
        }
    }))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    if mode == "pre":
        try:
            emit(decide_pre(read_stdin_json()))
        except PolicyError as exc:
            emit(("ask", f"LORM: policy present but unusable ({exc}) — "
                         "degrading to human approval"))
        except Exception as exc:  # fail-closed, never crash-open
            emit(("ask", f"LORM hook error: {type(exc).__name__}: {exc} — "
                         "degrading to human approval"))
        sys.exit(0)
    if mode == "post":
        try:
            run_post(read_stdin_json())
        except Exception as exc:  # never block a completed call
            print(f"lorm_gate post: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
    print(f"lorm_gate: unknown mode {mode!r} (use 'pre' or 'post')", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
