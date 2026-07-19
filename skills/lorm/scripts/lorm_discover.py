#!/usr/bin/env python3
"""LORM discovery — cluster unclassified actions, propose draft entries.

Usage:
    python3 lorm_discover.py [project_dir] [--json] [--window DAYS]
                             [--min-count N]

Reads .lorm/observations.jsonl (written by the enforcement hook for every
gated call that matched neither a policy capability nor a built-in
classifier — normalized skeletons only, never payloads), clusters the
records by (tool, skeleton), and for every cluster above the repetition
threshold emits a DRAFT capability entry:

  - entering at L3, the ceiling SPEC 4-3 allows for new registry entries
    ("lowest level consistent with their nature, and never above L3");
  - with a match block derived from the skeleton (placeholders become
    fnmatch wildcards);
  - flagging the verification gap: a freshly registered capability
    accumulates 'pending' records unless verification.expect (and, where
    mechanically checkable, a schema-1.4 verification.mechanical block)
    is declared.

The analyzer only proposes. It never writes the policy file (SPEC I-8) —
drafts are printed for human review, and applying an L3 entry makes the
hook DENY the formerly-silent action (raise to L4 consciously if you want
the approval dialog plus audit tracking instead).

Defaults: --window 30 (days of observations considered), --min-count 5
(repetitions required to propose). Exit codes: 0 ok (even with findings),
2 usage/environment error.
"""

import datetime
import json
import os
import sys

WINDOW_DAYS = 30
MIN_COUNT = 5
OBSERVATIONS_NAME = "observations.jsonl"
POLICY_CANDIDATES = (
    "lorm-policy.yaml", "lorm-policy.json",
    os.path.join(".lorm", "policy.yaml"), os.path.join(".lorm", "policy.json"),
)
PLACEHOLDERS = ("«ARG»", "«PATH»", "«N»", "«V»")
ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def load_policy(root):
    for name in POLICY_CANDIDATES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            text = open(path, encoding="utf-8").read()
            if path.endswith(".json"):
                return json.loads(text), path
            try:
                import yaml
            except ImportError:
                fail("policy is YAML but PyYAML is missing (pip install pyyaml)")
            return yaml.safe_load(text), path
    return None, None


def load_observations(policy, root):
    configured = ((policy or {}).get("audit") or {}).get("log") or os.path.join(
        ".lorm", "audit.jsonl")
    audit = configured if os.path.isabs(configured) else os.path.join(root, configured)
    path = os.path.join(os.path.dirname(audit), OBSERVATIONS_NAME)
    if not os.path.isfile(path):
        return [], path
    records = []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue  # observations carry no audit guarantee; skip quietly
    return records, path


def _sanitize_id_part(part):
    part = "".join(ch if ch in ID_CHARS else "-" for ch in part.lower())
    return part.strip("-") or "x"


def draft_id(tool, skeleton):
    """cmd.<argv0>.<subcommand> / fs.write.<top-dir> / mcp.<server>.<tool>."""
    if tool == "Bash":
        words = [w for w in skeleton.split() if not w.startswith(("«", "-", ">"))]
        parts = ["cmd"] + [_sanitize_id_part(w) for w in words[:2]]
        return ".".join(parts)
    if tool in ("Write", "Edit"):
        top = skeleton.split("/", 1)[0]
        if top.startswith("*"):
            top = "root"
        return f"fs.write.{_sanitize_id_part(top)}"
    if tool.startswith("mcp__"):
        name = tool.split("(", 1)[0]
        bits = name.split("__")
        server = bits[1] if len(bits) > 1 else "server"
        toolname = bits[2] if len(bits) > 2 else "tool"
        return f"mcp.{_sanitize_id_part(server)}.{_sanitize_id_part(toolname)}"
    return f"cmd.{_sanitize_id_part(tool)}"


def skeleton_to_pattern(skeleton):
    """Bash skeleton -> command_patterns draft: placeholders become '*'."""
    out = []
    for token in skeleton.split():
        for ph in PLACEHOLDERS:
            token = token.replace(ph, "*")
        out.append(token)
    return " ".join(out)


def build_draft(tool_group, skeleton, cluster, known_ids):
    tools = sorted(tool_group)
    cid = draft_id(tools[0], skeleton)
    match = {}
    if tools == ["Bash"]:
        match = {"tools": ["Bash"],
                 "command_patterns": [skeleton_to_pattern(skeleton)]}
    elif set(tools) <= {"Write", "Edit"}:
        match = {"tools": tools, "path_patterns": [skeleton]}
    else:  # MCP: skeleton is mcp__server__tool(field,names)
        match = {"tool_patterns": [skeleton.split("(", 1)[0]],
                 "x-DRAFT": "add input_patterns encoding the target scope "
                            "(bounds.targets are not hook-verifiable for MCP)"}
    draft = {
        "id": cid,
        "level": "L3",
        "description": (f"DRAFT — observed {cluster['count']} times in the "
                        f"window ({cluster['sessions']} session(s)), never "
                        f"classified"),
        "match": match,
        "bounds": {"targets": ["DRAFT — declare targets"]},
        "x-note-level": (
            "SPEC 4-3: new capabilities enter at <= L3 (entry directly at L5 "
            "is prohibited). NOTE: an applied L3 entry makes the hook DENY "
            "this action, which today passes through the normal permission "
            "dialog — raise to L4 consciously if you want the approval "
            "dialog plus audit tracking instead."),
        "x-note-verification": (
            "VERIFICATION GAP — once registered, executions accumulate as "
            "'pending' unless you add verification.expect (and a schema-1.4 "
            "verification.mechanical block where the outcome is mechanically "
            "checkable). See docs/hard-enforcement.md."),
    }
    if cid in known_ids:
        draft["x-note-collision"] = (
            f"a capability with id '{cid}' already exists in the policy — "
            f"these observations are the variants its match block does NOT "
            f"cover; extend that entry instead of adding a duplicate")
    return draft


def analyze(policy, records, now, window_days, min_count):
    policy = policy or {}
    cutoff = now - datetime.timedelta(days=window_days)
    known_ids = {c.get("id") for c in policy.get("capabilities") or []
                 if isinstance(c, dict)}

    # (tool-group key, skeleton) -> cluster; Write and Edit merge into one
    clusters = {}
    total = in_window = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        tool, skeleton = rec.get("tool"), rec.get("skeleton")
        if not tool or not skeleton or skeleton == "«UNPARSED»":
            continue
        total += 1
        ts = parse_ts(rec.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        in_window += 1
        group = ("Write", "Edit") if tool in ("Write", "Edit") else (tool,)
        key = (group, skeleton)
        c = clusters.setdefault(key, {
            "tools": sorted(group), "skeleton": skeleton, "count": 0,
            "first_seen": rec.get("timestamp"), "last_seen": rec.get("timestamp"),
            "session_set": set(),
        })
        c["count"] += 1
        c["first_seen"] = min(c["first_seen"], rec.get("timestamp") or "")
        c["last_seen"] = max(c["last_seen"], rec.get("timestamp") or "")
        if rec.get("x-session"):
            c["session_set"].add(rec["x-session"])

    proposals = []
    for (group, skeleton), c in sorted(clusters.items(),
                                       key=lambda kv: -kv[1]["count"]):
        c["sessions"] = len(c.pop("session_set")) or 1
        if c["count"] < min_count:
            continue
        c["draft"] = build_draft(group, skeleton, c, known_ids)
        proposals.append(c)

    return {"observations_total": total, "observations_in_window": in_window,
            "clusters_total": len(clusters)}, proposals


def yaml_snippet(obj, indent=0):
    """Small dependency-free YAML renderer for draft snippets."""
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                lines.append(yaml_snippet(value, indent + 1))
            else:
                lines.append(f"{pad}{key}: {json.dumps(value, ensure_ascii=False)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                body = yaml_snippet(item, indent + 1).lstrip()
                lines.append(f"{pad}- {body}")
            else:
                lines.append(f"{pad}- {json.dumps(item, ensure_ascii=False)}")
    return "\n".join(lines)


def render_text(summary, proposals, window_days, min_count):
    out = [f"LORM discovery — recurring unclassified actions, "
           f"last {window_days} days (threshold: {min_count})", ""]
    out.append(f"{summary['observations_in_window']} observation(s) in window "
               f"({summary['observations_total']} total, "
               f"{summary['clusters_total']} distinct shapes)")
    if not proposals:
        out += ["", "No cluster reaches the threshold. Nothing to propose."]
        return "\n".join(out)
    for c in proposals:
        out += ["", f"== {'+'.join(c['tools'])}: {c['skeleton']} =="]
        out.append(f"  seen {c['count']}x in {c['sessions']} session(s), "
                   f"{c['first_seen']} .. {c['last_seen']}")
        out.append("  draft (for human review — never self-applied, SPEC I-8):")
        out.append(yaml_snippet(c["draft"], indent=2))
    return "\n".join(out)


def main():
    args = list(sys.argv[1:])
    as_json, window, min_count = False, WINDOW_DAYS, MIN_COUNT
    root = os.getcwd()
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            as_json = True
        elif arg == "--window":
            i += 1
            window = int(args[i])
        elif arg == "--min-count":
            i += 1
            min_count = int(args[i])
        elif arg.startswith("--"):
            fail(f"unknown option {arg}")
        else:
            root = arg
        i += 1
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        fail(f"not a directory: {root}")

    policy, policy_path = load_policy(root)
    records, obs_path = load_observations(policy, root)
    now = datetime.datetime.now(datetime.timezone.utc)
    summary, proposals = analyze(policy, records, now, window, min_count)

    if as_json:
        print(json.dumps({
            "project": root, "policy": policy_path, "observations": obs_path,
            "window_days": window, "min_count": min_count,
            "summary": summary, "proposals": proposals,
        }, indent=2, ensure_ascii=False))
    else:
        if policy_path is None:
            print("note: no lorm-policy.yaml found — clustering observations only\n")
        print(render_text(summary, proposals, window, min_count))


if __name__ == "__main__":
    main()
