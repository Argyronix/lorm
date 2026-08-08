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
import subprocess
import sys
import time

GATED_TOOLS = {"Bash", "Write", "Edit"}


def is_gated_tool(tool):
    return tool in GATED_TOOLS or (isinstance(tool, str) and tool.startswith("mcp__"))
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
CONDITION_TIMEOUT_DEFAULT = 5
CONDITIONS_BUDGET_SECONDS = 8.0  # keep total below the 10s hook timeout
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
    if rel_path is None:
        # Outside the project root there is no project-relative form for a
        # path_patterns entry to cover (schema 1.5); the boolean flag is the
        # only policy-side equivalent of the fs.write.outside_project classifier.
        return tool in ("Write", "Edit") and bool(match.get("path_outside_project"))
    patterns = match.get("path_patterns") or []
    return bool(patterns) and any(
        fnmatch.fnmatchcase(rel_path, pat) for pat in patterns
    )


def stringify_input_value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def cap_matches_mcp(cap, tool, tool_input):
    """MCP matching (schema 1.2): tool_patterns vs the full tool name;
    every input_patterns field must exist in tool_input and match (AND)."""
    match = cap.get("match")
    if not isinstance(match, dict):
        return False
    tool_patterns = match.get("tool_patterns") or []
    if not tool_patterns or not any(
        fnmatch.fnmatchcase(tool, pat) for pat in tool_patterns
    ):
        return False
    for field, pattern in (match.get("input_patterns") or {}).items():
        if field not in tool_input:
            return False
        if not fnmatch.fnmatchcase(stringify_input_value(tool_input[field]), pattern):
            return False
    return True


def mcp_classifier_hit(classifiers, tool):
    for entry in classifiers:
        patterns = entry.get("tool_patterns") or []
        if patterns and any(fnmatch.fnmatchcase(tool, p) for p in patterns):
            return entry.get("capability")
    return None


_WILDCARD_CHARS = set("*?[]")


def pattern_specificity(pattern):
    """Literal (non-wildcard) character count — the specificity metric."""
    return sum(1 for ch in pattern if ch not in _WILDCARD_CHARS)


def _best_matching_specificity(patterns, texts):
    best = -1
    for pat in patterns or []:
        if any(fnmatch.fnmatchcase(t, pat) for t in texts):
            best = max(best, pattern_specificity(pat))
    return best


def cap_specificity(cap, tool, text=None, rel_path=None, tool_input=None):
    """Specificity of a capability's match against one concrete call."""
    match = cap.get("match") or {}
    if tool == "Bash":
        return _best_matching_specificity(
            match.get("command_patterns"), [text or ""])
    if tool in ("Write", "Edit"):
        score = _best_matching_specificity(
            match.get("path_patterns"), [rel_path or ""])
        # An outside-project flag match (schema 1.5) has no pattern to score;
        # give it minimal specificity so any patterned entry still wins ties.
        if score < 0 and rel_path is None and match.get("path_outside_project"):
            return 0
        return score
    score = _best_matching_specificity(match.get("tool_patterns"), [tool])
    for pattern in (match.get("input_patterns") or {}).values():
        score += pattern_specificity(pattern)
    return score


def select_most_specific(caps, tool, text=None, rel_path=None, tool_input=None):
    """When several capabilities match one call, the policy author's most
    specific entry is the intended classification (a narrow L5 exception
    inside a broad L4 catch-all must be reachable). Ties keep all matches
    and combine most-restrictively as before."""
    if len(caps) <= 1:
        return caps
    scores = [cap_specificity(c, tool, text, rel_path, tool_input) for c in caps]
    top = max(scores)
    return [c for c, s in zip(caps, scores) if s == top]


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


# --------------------------------------------------------------- conditions


def evaluate_conditions(cap, tool, tool_input, project_root):
    """Run executable condition checks (schema 1.3).

    Returns (failure_reason_or_None, checked_count, soft_count). A check
    passes iff its command exits 0; non-zero, timeout, or an exhausted
    overall budget degrade the action (caller emits 'ask'). Plain-string
    conditions stay agent-verified (soft)."""
    checked = soft = 0
    started = time.monotonic()
    for cond in cap.get("conditions") or []:
        if not (isinstance(cond, dict) and cond.get("check")):
            soft += 1
            continue
        text = cond.get("text") or cond["check"]
        remaining = CONDITIONS_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            return (f"conditions time budget exhausted before checking "
                    f"'{text}'", checked, soft)
        timeout = min(int(cond.get("timeout") or CONDITION_TIMEOUT_DEFAULT),
                      max(1, int(remaining)))
        env = dict(os.environ,
                   LORM_CAPABILITY=cap.get("id", ""),
                   LORM_TOOL_NAME=tool,
                   LORM_ACTION=summarize_action(tool, tool_input),
                   CLAUDE_PROJECT_DIR=project_root)
        try:
            proc = subprocess.run(cond["check"], shell=True, cwd=project_root,
                                  capture_output=True, text=True,
                                  timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return (f"condition check timed out after {timeout}s: '{text}'",
                    checked, soft)
        except OSError as exc:
            return (f"condition check could not run ({exc}): '{text}'",
                    checked, soft)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            suffix = f" — {detail[0][:80]}" if detail else ""
            return (f"condition not met: '{text}' (check exit "
                    f"{proc.returncode}{suffix})", checked, soft)
        checked += 1
    return None, checked, soft


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

    failure, checked, soft = evaluate_conditions(cap, tool, tool_input,
                                                 project_root)
    if failure:
        return ("ask", f"LORM: `{cid}` L5 entry valid but {failure} — "
                       "degrading to L4 (SPEC 13-1)")
    if checked and soft:
        cond_note = (f"; {checked} condition check(s) passed, "
                     f"{soft} condition(s) remain agent-verified")
    elif checked:
        cond_note = f"; {checked} condition check(s) passed"
    elif soft:
        cond_note = "; conditions[] remain agent-verified (soft)"
    else:
        cond_note = ""

    pol = cap.get("policy") or {}
    return ("allow",
            f"LORM: authorized by policy `{cid}` v{pol.get('version', '?')} "
            f"(expires {pol.get('expires')}){rate_note}{cond_note}")


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
    if not is_gated_tool(tool):
        return None
    tool_input = payload.get("tool_input") or {}
    project_root = find_project_dir(payload)
    cwd = os.path.realpath(payload.get("cwd") or project_root)

    policy_path = find_policy_file(project_root)
    if policy_path is None:
        return None  # passive: no policy, no opinion

    policy = load_policy(policy_path)  # PolicyError handled by caller
    audit_path = audit_log_path(policy, project_root)
    touch_hook_active(audit_path)
    now = utc_now()

    bash_texts, bash_segments = [], None
    rel_path, rel_outside = None, False
    if tool == "Bash":
        command = tool_input.get("command") or ""
        if not command.strip():
            return None
        bash_texts, bash_segments = bash_match_texts(command)
    elif tool in ("Write", "Edit"):
        raw = tool_input.get("file_path") or ""
        if not raw:
            return None
        rel_path, _ = norm_path(raw, cwd, project_root)
        rel_outside = rel_path is None
    # MCP tools (mcp__*) need no pre-extraction; matching is by tool name
    # and input_patterns. Self-protection (P1/P2) is not evaluable for MCP
    # filesystem servers — documented limitation in docs/hard-enforcement.md.

    decisions = [
        self_protection(tool, tool_input, bash_segments, cwd, project_root,
                        policy_path, audit_path)
        if tool in GATED_TOOLS else None
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
            caps_here = select_most_specific(caps_here, tool, text=text)
            for cap in caps_here:
                decisions.append(decide_for_capability(
                    cap, policy, tool, tool_input,
                    [seg] if seg else None,
                    cwd, project_root, audit_path, now))
            if not caps_here:
                hit = classifier_hit(classifiers, tool, [text], False)
                if hit:
                    decisions.append(defaults_decision(hit))
    elif tool.startswith("mcp__"):
        caps_here = [c for c in caps if cap_matches_mcp(c, tool, tool_input)]
        caps_here = select_most_specific(caps_here, tool, tool_input=tool_input)
        for cap in caps_here:
            decisions.append(decide_for_capability(
                cap, policy, tool, tool_input, None,
                cwd, project_root, audit_path, now))
        if not caps_here:
            hit = mcp_classifier_hit(classifiers, tool)
            if hit:
                decisions.append(defaults_decision(hit))
    else:
        caps_here = [c for c in caps if cap_matches_path(c, tool, rel_path)]
        caps_here = select_most_specific(caps_here, tool, rel_path=rel_path)
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


def append_jsonl(path, record):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except ImportError:  # non-POSIX: best-effort append
            fh.write(line)


def touch_hook_active(audit_path):
    """Tell soft consumers the hook is live here.

    Written on the first gated pre call, not on the first audit append. The
    skill checks for this marker in the same turn as the action it just took,
    and in a fresh project the post-side append had not landed yet — so the
    skill concluded no hook was running and appended its own execution record,
    duplicating the hook's and double-counting the rate limit. Announcing at
    gate time removes the race: by the time the model can look, the marker is
    there. Best-effort by design — bookkeeping must never affect a decision.
    """
    directory = os.path.dirname(audit_path) or "."
    marker = os.path.join(directory, "hook-active")
    if os.path.exists(marker):
        return
    try:
        os.makedirs(directory, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(
                "LORM enforcement hook is active in this project.\n"
                "Soft consumers (the agent skill) must append only "
                "verification records, not execution records. See "
                "skills/lorm/references/policy-format.md.\n")
    except OSError:
        pass


def append_audit(audit_path, record):
    append_jsonl(audit_path, record)
    touch_hook_active(audit_path)


def summarize_action(tool, tool_input):
    if tool == "Bash":
        return (tool_input.get("command") or "")[:300]
    if tool.startswith("mcp__"):
        return f"{tool} {json.dumps(tool_input, ensure_ascii=False)}"[:300]
    return f"{tool} {tool_input.get('file_path', '')}"[:300]


# ------------------------------------------------------------- observations


OBSERVATIONS_LOG_NAME = "observations.jsonl"
OBSERVATIONS_MAX_BYTES = 512 * 1024
_SUBCOMMAND_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def _skeleton_bash_segment(seg, cwd):
    """Normalize one wrapper-stripped Bash segment into a clustering key.

    Literal: argv[0], the first non-flag token when it looks like a
    subcommand, flag names. Placeholders: «PATH» (contains / or resolves
    against cwd), «N» (all digits), «V» (a flag's =value), «ARG» (anything
    else). Consecutive identical placeholders collapse, so variadic arg
    lists cluster together."""
    out = [seg[0]]
    sub_taken = False
    for tok in seg[1:]:
        if tok in REDIRECT_TOKENS:
            out.append(tok)
        elif tok.startswith("-"):
            name, eq, _ = tok.partition("=")
            out.append(name + "=«V»" if eq else name)
        elif "/" in tok or os.path.exists(os.path.join(cwd, tok)):
            out.append("«PATH»")
            sub_taken = True
        elif tok.isdigit():
            out.append("«N»")
            sub_taken = True
        elif (not sub_taken and tok[:1].isalpha()
              and all(ch in _SUBCOMMAND_CHARS for ch in tok)):
            out.append(tok)
            sub_taken = True
        else:
            out.append("«ARG»")
            sub_taken = True
    collapsed = []
    for tok in out:
        if collapsed and tok == collapsed[-1] and tok.startswith("«"):
            continue
        collapsed.append(tok)
    return " ".join(collapsed)


def skeletonize(tool, tool_input, cwd, project_root):
    """Normalized shape(s) of a gated call — never values or payloads.

    Bash: one skeleton per shell segment (same segmentation the matcher
    uses, so a skeleton is a natural command_patterns draft). Write/Edit:
    project-relative directory with a generalized basename ('src/*.py') —
    already a valid path_patterns draft. MCP: tool name plus sorted input
    field names."""
    if tool == "Bash":
        command = tool_input.get("command") or ""
        tokens = tokenize_bash(command)
        if tokens is None:
            return ["«UNPARSED»"]
        segments = [strip_wrappers(s) for s in split_segments(tokens)]
        return [_skeleton_bash_segment(s, cwd) for s in segments if s]
    if tool in ("Write", "Edit"):
        raw = tool_input.get("file_path") or ""
        if not raw:
            return []
        rel, _ = norm_path(raw, cwd, project_root)
        if rel is None:
            return []  # outside-project writes hit fs.write.outside_project
        dirname, basename = os.path.split(rel)
        _, ext = os.path.splitext(basename)
        pattern = f"*{ext}" if ext else "*"
        return [f"{dirname}/{pattern}" if dirname else pattern]
    if tool.startswith("mcp__") and isinstance(tool_input, dict):
        fields = ",".join(sorted(tool_input.keys()))
        return [f"{tool}({fields})"]
    return []


def record_observations(audit_path, policy_path, tool, tool_input, cwd,
                        project_root, session_id, now):
    """Log a gated call that matched neither a capability nor a classifier.

    Written to observations.jsonl next to the audit log — a separate file
    on purpose: the append-only guarantee (I-6) belongs to audit.jsonl and
    its named-capability records; observations may be truncated. Size-capped
    (oldest half dropped past OBSERVATIONS_MAX_BYTES). Best-effort: any
    failure is swallowed, post never fails a completed call."""
    try:
        raw = ""
        if isinstance(tool_input, dict):
            raw = tool_input.get("command") or tool_input.get("file_path") or ""
        noise = (".lorm", os.path.basename(policy_path or ""),
                 "audit.jsonl", OBSERVATIONS_LOG_NAME)
        if any(n and n in raw for n in noise):
            return  # the skill's own log/policy traffic is not discovery signal
        skeletons = []
        for skeleton in skeletonize(tool, tool_input, cwd, project_root):
            if skeleton not in skeletons:
                skeletons.append(skeleton)
        if not skeletons:
            return
        obs_path = os.path.join(os.path.dirname(audit_path),
                                OBSERVATIONS_LOG_NAME)
        try:
            if os.path.getsize(obs_path) > OBSERVATIONS_MAX_BYTES:
                lines = open(obs_path, encoding="utf-8").read().splitlines()
                with open(obs_path, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(lines[len(lines) // 2:]) + "\n")
        except OSError:
            pass  # missing file: nothing to trim
        for skeleton in skeletons:
            append_jsonl(obs_path, {
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tool": tool,
                "skeleton": skeleton,
                "x-session": session_id,
            })
    except Exception:
        pass


# ------------------------------------------------- mechanical verification


PENDING_THRESHOLDS = (10, 25, 50, 100)


def extract_output(payload):
    """Return (output_text, exit_code_or_None) from the post payload.

    Claude Code's field names vary by version: the result arrives as
    `tool_output` or `tool_response`, either a plain string or a dict.
    An exit code is recoverable only from dict shapes that carry one;
    absent means None — mechanical exit_code checks then stay 'pending'."""
    raw = payload.get("tool_output")
    if raw is None:
        raw = payload.get("tool_response")
    if isinstance(raw, dict):
        exit_code = None
        for key in ("exit_code", "exitCode", "returncode", "returnCode", "code"):
            value = raw.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                exit_code = value
                break
        if exit_code is None and (raw.get("interrupted") is True
                                  or raw.get("is_error") is True
                                  or raw.get("isError") is True):
            exit_code = -1  # known-failed; exact code unknown
        text = raw.get("stdout") or raw.get("output") or ""
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False)
        stderr = raw.get("stderr")
        if isinstance(stderr, str) and stderr:
            text = f"{text}\n{stderr}" if text else stderr
        if not text:
            text = json.dumps(raw, ensure_ascii=False)
        return text, exit_code
    if isinstance(raw, str):
        return raw, None
    if raw is None:
        return "", None
    return json.dumps(raw, ensure_ascii=False), None


def _mech_target_path(value, tool_input, cwd, project_root):
    """Resolve a mechanical-check path; None when not resolvable.

    The literal token $TOOL_FILE means the Write/Edit file_path (resolved
    like the tool resolves it, against cwd); literal paths resolve against
    the project root."""
    if value == "$TOOL_FILE":
        raw = tool_input.get("file_path")
        if not raw:
            return None
        _, real = norm_path(raw, cwd, project_root)
        return real
    absolute = value if os.path.isabs(value) else os.path.join(project_root, value)
    return os.path.realpath(absolute)


def evaluate_mechanical(cap, tool, tool_input, output, exit_code, cwd, project_root):
    """Evaluate a capability's verification.mechanical checks (schema 1.4).

    Returns (status, detail). All checks pass -> ("verified", detail); any
    check fails -> ("failed", which); a check that cannot be evaluated is
    unknown — no failures but any unknown leaves ("pending", None), keeping
    the agent-driven verification path open. Fixed vocabulary, implicit
    AND, no subprocesses. Never raises (post must not block)."""
    try:
        checks = ((cap.get("verification") or {}).get("mechanical") or {}).get("checks")
        if not isinstance(checks, list) or not checks:
            return "pending", None
        passed = unknown = 0
        for check in checks:
            if not isinstance(check, dict) or len(check) != 1:
                unknown += 1
                continue
            kind, value = next(iter(check.items()))
            if kind == "file_exists" and isinstance(value, str) and value:
                target = _mech_target_path(value, tool_input, cwd, project_root)
                if target is None:
                    unknown += 1
                elif os.path.exists(target):
                    passed += 1
                else:
                    return "failed", f"file_exists failed: {value}"
            elif kind == "file_contains" and isinstance(value, dict):
                path, substring = value.get("path"), value.get("substring")
                if not (isinstance(path, str) and path
                        and isinstance(substring, str) and substring):
                    unknown += 1
                    continue
                target = _mech_target_path(path, tool_input, cwd, project_root)
                if target is None:
                    unknown += 1
                    continue
                if not os.path.exists(target):
                    return "failed", f"file_contains failed: {path} does not exist"
                try:
                    with open(target, encoding="utf-8", errors="replace") as fh:
                        content = fh.read(1 << 20)
                except OSError:
                    unknown += 1
                    continue
                if substring in content:
                    passed += 1
                else:
                    return "failed", f"file_contains failed: {substring!r} not in {path}"
            elif kind == "output_contains" and isinstance(value, str) and value:
                if not output:
                    unknown += 1
                elif value in output:
                    passed += 1
                else:
                    return "failed", f"output_contains failed: {value!r} not in output"
            elif (kind == "exit_code" and isinstance(value, int)
                  and not isinstance(value, bool)):
                if exit_code is None:
                    unknown += 1
                elif exit_code == value:
                    passed += 1
                else:
                    return "failed", f"exit_code failed: expected {value}, got {exit_code}"
            else:
                unknown += 1
        if unknown:
            return "pending", None
        return "verified", f"{passed} mechanical check(s) passed"
    except Exception:
        return "pending", None


def count_verification_backlog(audit_path, capability):
    """Return (pending, verified) execution counts for one capability.

    A later skill-written verification record (carrying x-verifies)
    supersedes the execution record's own verified field, mirroring the
    join lorm_review.py performs."""
    try:
        lines = open(audit_path, encoding="utf-8").read().splitlines()
    except OSError:
        return 0, 0
    vmap, execs = {}, []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("capability") != capability:
            continue
        if "x-verifies" in rec:
            vmap[rec["x-verifies"]] = rec.get("verified", "pending")
        elif rec.get("action"):
            execs.append(rec)
    pending = verified = 0
    for rec in execs:
        status = vmap.get(rec.get("timestamp")) or rec.get("verified") or "pending"
        if status == "pending":
            pending += 1
        elif status == "verified":
            verified += 1
    return pending, verified


def run_post(payload):
    tool = payload.get("tool_name")
    if not is_gated_tool(tool):
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
    elif tool in ("Write", "Edit"):
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
    elif tool.startswith("mcp__"):
        matched = [c for c in caps if cap_matches_mcp(c, tool, tool_input)]
    else:
        matched = [c for c in caps if cap_matches_path(c, tool, rel_path)]
    if matched:
        if len(matched) > 1:
            def _score(c):
                if tool == "Bash":
                    return max(cap_specificity(c, tool, text=t)
                               for t in bash_texts)
                if tool.startswith("mcp__"):
                    return cap_specificity(c, tool, tool_input=tool_input)
                return cap_specificity(c, tool, rel_path=rel_path)
            matched.sort(key=_score, reverse=True)
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
        if tool.startswith("mcp__"):
            hit = mcp_classifier_hit(load_classifiers(), tool)
        else:
            hit = classifier_hit(load_classifiers(), tool, bash_texts, rel_outside)
        if hit:
            capability = hit
            level = "L4"  # it executed, so a human approved it
            authorizer = f"human:session {payload.get('session_id', '?')}"

    if capability is None:
        # Benign call: no audit record, but leave a discovery trace —
        # recurring unclassified actions become /lorm-review draft entries.
        record_observations(audit_path, policy_path, tool, tool_input, cwd,
                            project_root, payload.get("session_id", ""), now)
        return None

    output, exit_code = extract_output(payload)
    verified, verify_detail = "pending", None
    if matched:  # mechanical checks live only on policy entries, never classifier hits
        verified, verify_detail = evaluate_mechanical(
            cap, tool, tool_input, output, exit_code, cwd, project_root)
    record = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capability": capability,
        "level": level,
        "authorizer": authorizer,
        "action": summarize_action(tool, tool_input),
        "params": {"tool": tool, "cwd": cwd},
        "diagnosis_ref": "unavailable-to-hook",
        "outcome": output[:300],
        "verified": verified,
        "x-writer": "lorm-hook",
        "x-session": payload.get("session_id", ""),
    }
    if verify_detail:
        record["x-verified-by"] = "lorm-hook-mechanical"
        record["x-verify-detail"] = verify_detail[:200]
    append_audit(audit_path, record)

    if verified == "failed":
        return (f"LORM: mechanical verification FAILED for `{capability}`: "
                f"{verify_detail} — a failed verification is a demotion "
                f"trigger (SPEC 6-5); run /lorm:lorm-review")
    if verified == "pending":
        pending, ok = count_verification_backlog(audit_path, capability)
        if pending in PENDING_THRESHOLDS and ok == 0:
            return (f"LORM: `{capability}` has {pending} execution(s) pending "
                    f"verification and 0 verified — trust-lifecycle progress "
                    f"is stalled; add verification.mechanical (schema 1.4) "
                    f"where the outcome is mechanically checkable, or run "
                    f"the skill's verify step (/lorm:lorm-review explains)")
    return None


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
            message = run_post(read_stdin_json())
            if message:
                print(json.dumps({"systemMessage": message}))
        except Exception as exc:  # never block a completed call
            print(f"lorm_gate post: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
    print(f"lorm_gate: unknown mode {mode!r} (use 'pre' or 'post')", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
