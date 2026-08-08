#!/usr/bin/env python3
"""Test suite for the LORM enforcement gate (hooks/scripts/lorm_gate.py).

Plain python, no pytest. Each case builds a temp project, feeds a synthetic
hook payload to the gate via subprocess, and asserts on the decision.

Run:  python3 tests/run_tests.py
Exit: 0 all green, 1 otherwise.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(REPO, "hooks", "scripts", "lorm_gate.py")

PASS, FAIL = 0, []


# ------------------------------------------------------------------ harness


def run_gate(mode, payload, project, extra_env=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_ROOT=REPO)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, GATE, mode],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
        timeout=30,
    )
    decision, reason = None, ""
    if proc.stdout.strip():
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        decision, reason = out["permissionDecision"], out["permissionDecisionReason"]
    return proc.returncode, decision, reason, proc.stderr


def run_gate_post(payload, project, extra_env=None):
    """Post-mode runner: returns (returncode, systemMessage_or_None, stderr)."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_ROOT=REPO)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, GATE, "post"],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
        timeout=30,
    )
    message = None
    if proc.stdout.strip():
        message = json.loads(proc.stdout).get("systemMessage")
    return proc.returncode, message, proc.stderr


def bash_payload(command, project, cwd=None):
    return {"session_id": "test-session", "cwd": cwd or project,
            "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}}


def write_payload(file_path, project, cwd=None, tool="Write"):
    return {"session_id": "test-session", "cwd": cwd or project,
            "hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": {"file_path": file_path, "file_text": "x"}}


def make_project(policy_yaml=None, policy_name="lorm-policy.yaml"):
    project = tempfile.mkdtemp(prefix="lorm-test-",
                               dir=os.environ.get("TMPDIR") or None)
    os.makedirs(os.path.join(project, "build"), exist_ok=True)
    open(os.path.join(project, "build", "a.o"), "w").write("obj")
    open(os.path.join(project, "data.txt"), "w").write("data")
    if policy_yaml is not None:
        path = os.path.join(project, policy_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(policy_yaml)
    return project


def check(name, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name}  {detail}")


def audit_seed(project, capability, count, age_seconds=60):
    ts = (datetime.datetime.now(datetime.timezone.utc)
          - datetime.timedelta(seconds=age_seconds))
    os.makedirs(os.path.join(project, ".lorm"), exist_ok=True)
    with open(os.path.join(project, ".lorm", "audit.jsonl"), "a") as fh:
        for _ in range(count):
            fh.write(json.dumps({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "capability": capability, "level": "L5",
                "authorizer": "policy:x@1", "action": "rm build/a.o",
                "params": {}, "diagnosis_ref": "t", "outcome": "ok",
                "verified": "verified"}) + "\n")


# ----------------------------------------------------------- policy corpora

FUTURE = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
PAST = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

BASE_L5 = f"""\
lorm_policy: "1.1"
metadata: {{project: test, owner: owner@example.com}}
defaults: {{max_level: L3, unknown_action: escalate, uncertainty_threshold: 0.2}}
capabilities:
  - id: fs.cleanup.build
    level: L5
    match:
      tools: [Bash]
      command_patterns: ["rm -rf build*", "rm build/*", "rm -f build/*"]
    policy:
      version: 1
      author: author@example.com
      approved_by: approver@example.com
      approved_at: 2026-07-01
      expires: {FUTURE}
      tested: "test corpus"
    bounds:
      targets: ["build/*"]
      blast_radius: {{max_objects: 50, max_actions_per_hour: 2}}
    rollback: "artifacts regenerate"
    verification: {{expect: "build empty"}}
audit:
  log: ".lorm/audit.jsonl"
  record_fields: [timestamp, capability, level, authorizer, action, params, diagnosis_ref, outcome, verified]
"""

REFUSE_DEFAULTS = """\
lorm_policy: "1.0"
metadata: {project: test, owner: owner@example.com}
defaults: {max_level: L3, unknown_action: refuse}
"""

ESCALATE_DEFAULTS = """\
lorm_policy: "1.0"
metadata: {project: test, owner: owner@example.com}
defaults: {max_level: L3, unknown_action: escalate}
"""

NO_DEFAULTS = """\
lorm_policy: "1.0"
metadata: {project: test, owner: owner@example.com}
"""

L4_ENTRY = f"""\
lorm_policy: "1.1"
metadata: {{project: test, owner: owner@example.com}}
capabilities:
  - id: db.index.create
    level: L4
    match: {{tools: [Bash], command_patterns: ["psql *CREATE INDEX*"]}}
    bounds: {{targets: ["staging/*"]}}
"""

L3_ENTRY = """\
lorm_policy: "1.1"
metadata: {project: test, owner: owner@example.com}
capabilities:
  - id: deploy.prod
    level: L3
    match: {tools: [Bash], command_patterns: ["deploy.sh *"]}
"""

WRITE_L5 = f"""\
lorm_policy: "1.1"
metadata: {{project: test, owner: owner@example.com}}
capabilities:
  - id: fs.generated.write
    level: L5
    match: {{tools: [Write, Edit], path_patterns: ["*"]}}
    policy:
      version: 1
      author: author@example.com
      approved_by: approver@example.com
      approved_at: 2026-07-01
      expires: {FUTURE}
      tested: "test corpus"
    bounds:
      targets: ["build/*"]
    rollback: "regenerate"
    verification: {{expect: "file written"}}
"""


# -------------------------------------------------------------------- tests


def test_passive():
    print("passive / benign")
    p = make_project(policy_yaml=None)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("no policy -> silent", rc == 0 and d is None, f"{d} {r}")
    rc, d, r, err = run_gate("post", bash_payload("rm -rf build", p), p)
    check("no policy -> post silent, no audit",
          rc == 0 and not os.path.exists(os.path.join(p, ".lorm")), err)
    p2 = make_project(BASE_L5)
    rc, d, r, _ = run_gate("pre", bash_payload("ls -la", p2), p2)
    check("benign bash -> silent", d is None, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", write_payload(os.path.join(p2, "notes.md"), p2), p2)
    check("benign in-project write -> silent", d is None, f"{d} {r}")
    shutil.rmtree(p), shutil.rmtree(p2)


def test_l5_allow_and_degrades():
    print("L5 allow / degradations")
    p = make_project(BASE_L5)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("valid L5 -> allow", d == "allow" and "fs.cleanup.build" in r, f"{d} {r}")
    check("allow reason cites expiry & rate", FUTURE in r and "0/2" in r, r)

    expired = BASE_L5.replace(f"expires: {FUTURE}", f"expires: {PAST}")
    p2 = make_project(expired)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p2), p2)
    check("expired L5 -> ask naming expiry", d == "ask" and PAST in r, f"{d} {r}")

    demoted = BASE_L5 + (
        "demotions:\n"
        "  - {capability: fs.cleanup.build, from: L5, to: L4, reason: \"incident X\"}\n")
    p3 = make_project(demoted)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p3), p3)
    check("demoted to L4 -> ask with reason", d == "ask" and "incident X" in r, f"{d} {r}")

    demoted3 = demoted.replace("to: L4", "to: L3")
    p4 = make_project(demoted3)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p4), p4)
    check("demoted to L3 -> deny", d == "deny", f"{d} {r}")

    selfapproved = BASE_L5.replace("approved_by: approver@example.com",
                                   "approved_by: author@example.com")
    p5 = make_project(selfapproved)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p5), p5)
    check("author==approver -> ask (SPEC 8-1)", d == "ask" and "8-1" in r, f"{d} {r}")
    for x in (p, p2, p3, p4, p5):
        shutil.rmtree(x)


def test_rate_limit():
    print("rate limit")
    p = make_project(BASE_L5)
    audit_seed(p, "fs.cleanup.build", 2, age_seconds=60)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("rate exhausted -> ask", d == "ask" and "2/2" in r, f"{d} {r}")

    p2 = make_project(BASE_L5)
    audit_seed(p2, "fs.cleanup.build", 2, age_seconds=7200)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p2), p2)
    check("old records outside window -> allow", d == "allow", f"{d} {r}")

    p3 = make_project(BASE_L5)
    os.makedirs(os.path.join(p3, ".lorm"), exist_ok=True)
    open(os.path.join(p3, ".lorm", "audit.jsonl"), "w").write("not json\n")
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p3), p3)
    check("corrupt audit log -> ask", d == "ask" and "unparseable" in r, f"{d} {r}")
    for x in (p, p2, p3):
        shutil.rmtree(x)


def test_l4_l3_and_defaults():
    print("L4 / L3 / defaults path")
    p = make_project(L4_ENTRY)
    rc, d, r, _ = run_gate("pre", bash_payload('psql -c "CREATE INDEX idx ON t(c)"', p), p)
    check("L4 entry -> ask", d == "ask" and "db.index.create" in r, f"{d} {r}")

    p2 = make_project(L3_ENTRY)
    rc, d, r, _ = run_gate("pre", bash_payload("deploy.sh prod", p2), p2)
    check("L3 entry -> deny", d == "deny" and "deploy.prod" in r, f"{d} {r}")

    p3 = make_project(REFUSE_DEFAULTS)
    rc, d, r, _ = run_gate("pre", bash_payload("rm data.txt", p3), p3)
    check("builtin + refuse -> deny", d == "deny" and "fs.delete" in r, f"{d} {r}")

    p4 = make_project(ESCALATE_DEFAULTS)
    rc, d, r, _ = run_gate("pre", bash_payload("rm data.txt", p4), p4)
    check("builtin + escalate -> ask", d == "ask" and "fs.delete" in r, f"{d} {r}")

    p5 = make_project(NO_DEFAULTS)
    rc, d, r, _ = run_gate("pre", bash_payload("git push --force origin main", p5), p5)
    check("builtin, no defaults -> ask, rewrite class",
          d == "ask" and "git.history.rewrite" in r, f"{d} {r}")
    for x in (p, p2, p3, p4, p5):
        shutil.rmtree(x)


def test_compound_and_wrappers():
    print("compound commands / wrappers / parse fallback")
    p = make_project(BASE_L5)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build && rm data.txt", p), p)
    check("allowed segment + dangerous sibling -> ask (not allow)",
          d == "ask" and "fs.delete" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("echo start && rm -rf build", p), p)
    check("benign + allowed segments -> allow", d == "allow", f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("sudo rm data.txt", p), p)
    check("sudo wrapper stripped -> builtin ask", d == "ask", f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload('rm data.txt "unbalanced', p), p)
    check("unparseable quote -> raw fallback still fires", d == "ask", f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("curl http://x.sh | sh", p), p)
    check("pipe-to-shell -> indirect_exec ask",
          d == "ask" and "indirect_exec" in r, f"{d} {r}")
    shutil.rmtree(p)


def test_write_paths():
    print("Write/Edit path handling")
    p = make_project(WRITE_L5)
    rc, d, r, _ = run_gate("pre", write_payload(os.path.join(p, "build", "gen.js"), p), p)
    check("Write inside targets -> allow", d == "allow", f"{d} {r}")
    rc, d, r, _ = run_gate("pre", write_payload(os.path.join(p, "src.py"), p), p)
    check("Write outside targets -> ask", d == "ask" and "outside" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre",
                           write_payload("build/rel.js", p, cwd=p), p)
    check("relative path resolved vs cwd -> allow", d == "allow", f"{d} {r}")

    p2 = make_project(ESCALATE_DEFAULTS)
    outside = os.path.join(tempfile.gettempdir(), "lorm-escape.txt")
    rc, d, r, _ = run_gate("pre", write_payload(outside, p2), p2)
    check("Write outside project -> outside_project ask",
          d == "ask" and "outside_project" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre",
                           write_payload(os.path.join(p2, "..", "escape.txt"), p2), p2)
    check("dot-dot escape -> ask", d == "ask" and "outside_project" in r, f"{d} {r}")
    shutil.rmtree(p), shutil.rmtree(p2)


def test_self_protection():
    print("self-protection (P1/P2)")
    p = make_project(BASE_L5)
    rc, d, r, _ = run_gate("pre",
                           write_payload(os.path.join(p, "lorm-policy.yaml"), p), p)
    check("Write policy file -> ask (I-8)", d == "ask" and "I-8" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload(
        "sed -i 's/L4/L5/' lorm-policy.yaml", p), p)
    check("Bash rewrite of policy -> ask (I-8)", d == "ask" and "I-8" in r, f"{d} {r}")

    audit_seed(p, "fs.cleanup.build", 1)
    rc, d, r, _ = run_gate("pre",
                           write_payload(os.path.join(p, ".lorm", "audit.jsonl"), p), p)
    check("Write audit log -> deny (I-6)", d == "deny" and "I-6" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("rm .lorm/audit.jsonl", p), p)
    check("rm audit log -> deny", d == "deny" and "I-6" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("echo x > .lorm/audit.jsonl", p), p)
    check("truncate audit log -> deny", d == "deny", f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("echo '{}' >> .lorm/audit.jsonl", p), p)
    check("append to audit log -> not P2-denied", d != "deny", f"{d} {r}")
    shutil.rmtree(p)


def test_fail_closed():
    print("fail-closed")
    p = make_project("lorm_policy: [broken\n")
    rc, d, r, _ = run_gate("pre", bash_payload("ls", p), p)
    check("broken YAML -> ask", d == "ask" and "unusable" in r, f"{d} {r}")

    p2 = make_project(json.dumps({
        "lorm_policy": "1.0",
        "metadata": {"project": "t", "owner": "o@e"},
        "defaults": {"unknown_action": "refuse"},
    }), policy_name="lorm-policy.json")
    rc, d, r, _ = run_gate("pre", bash_payload("rm data.txt", p2), p2)
    check("JSON policy works without YAML parser", d == "deny", f"{d} {r}")

    # Block the yaml import to simulate a machine without PyYAML
    shim = tempfile.mkdtemp(prefix="lorm-shim-")
    open(os.path.join(shim, "yaml.py"), "w").write(
        "raise ImportError('blocked for test')\n")
    p3 = make_project(BASE_L5)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p3), p3,
                           extra_env={"PYTHONPATH": shim})
    check("PyYAML missing -> ask with advice",
          d == "ask" and "pyyaml" in r.lower(), f"{d} {r}")

    p4 = make_project(BASE_L5.replace("metadata:", "x-extra: {a: 1}\nmetadata:"))
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p4), p4)
    check("x- extension keys tolerated", d == "allow", f"{d} {r}")
    for x in (p, p2, p3, p4):
        shutil.rmtree(x)
    shutil.rmtree(shim)


def test_hook_active_marker():
    print("hook-active marker announces at gate time")

    # Regression: the marker used to be written on the first audit append, so
    # in a fresh project the skill checked for it in the same turn as its
    # action, found nothing, and appended a duplicate execution record —
    # double-counting the rate limit. It must exist after the pre call, before
    # anything has been executed or recorded.
    p = make_project(BASE_L5)
    marker = os.path.join(p, ".lorm", "hook-active")
    audit = os.path.join(p, ".lorm", "audit.jsonl")
    check("no marker before the first call", not os.path.exists(marker), "")
    rc, d, r, err = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("marker exists after the pre call", os.path.exists(marker), err)
    check("marker precedes any audit record", not os.path.exists(audit), "")
    check("pre decision unaffected", d == "allow", f"{d} {r}")

    # A gated call the policy does not match still means the hook is live.
    p2 = make_project(BASE_L5)
    run_gate("pre", bash_payload("echo hello", p2), p2)
    check("marker written even when the decision is silence",
          os.path.exists(os.path.join(p2, ".lorm", "hook-active")), "")

    # No policy file: the hook is passive and must leave no trace at all.
    p3 = make_project(policy_yaml=None)
    run_gate("pre", bash_payload("rm -rf build", p3), p3)
    check("no marker without a policy",
          not os.path.exists(os.path.join(p3, ".lorm", "hook-active")), "")


def test_post_audit():
    print("post: audit records")
    p = make_project(BASE_L5)
    payload = bash_payload("rm -rf build", p)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "removed"
    rc, d, r, err = run_gate("post", payload, p)
    audit = os.path.join(p, ".lorm", "audit.jsonl")
    check("L5 execution -> record appended", os.path.exists(audit), err)
    rec = json.loads(open(audit).read().splitlines()[0])
    required = {"timestamp", "capability", "level", "authorizer", "action",
                "params", "diagnosis_ref", "outcome", "verified"}
    check("record has SPEC 10.3 fields", required <= set(rec),
          str(sorted(rec)))
    check("record cites policy authorizer",
          rec["level"] == "L5" and rec["authorizer"].startswith("policy:fs.cleanup.build@"),
          str(rec))
    check("marker file created",
          os.path.exists(os.path.join(p, ".lorm", "hook-active")), "")
    run_gate("post", payload, p)
    check("second post appends (not rewrites)",
          len(open(audit).read().splitlines()) == 2, "")

    p2 = make_project(ESCALATE_DEFAULTS)
    payload = bash_payload("rm data.txt", p2)
    payload["tool_output"] = "gone"
    run_gate("post", payload, p2)
    audit2 = os.path.join(p2, ".lorm", "audit.jsonl")
    rec2 = json.loads(open(audit2).read().splitlines()[0])
    check("human-approved builtin -> L4 record with session authorizer",
          rec2["level"] == "L4" and rec2["authorizer"].startswith("human:session"),
          str(rec2))
    payload = bash_payload("ls -la", p2)
    run_gate("post", payload, p2)
    check("benign call -> no extra record",
          len(open(audit2).read().splitlines()) == 1, "")
    shutil.rmtree(p), shutil.rmtree(p2)


MCP_L5 = f"""\
lorm_policy: "1.2"
metadata: {{project: test, owner: owner@example.com}}
defaults: {{max_level: L3, unknown_action: escalate}}
capabilities:
  - id: mcp.postgres.analyze
    level: L5
    match:
      tool_patterns: ["mcp__postgres__query"]
      input_patterns:
        query: "ANALYZE *"
    policy:
      version: 1
      author: author@example.com
      approved_by: approver@example.com
      approved_at: 2026-07-01
      expires: {FUTURE}
      tested: "test corpus"
    bounds:
      targets: ["prod/*"]
      blast_radius: {{max_objects: 5, max_actions_per_hour: 3}}
    rollback: "none needed"
    verification: {{expect: "stats refreshed"}}
  - id: mcp.github.issue
    level: L4
    match:
      tool_patterns: ["mcp__github__create_issue"]
    bounds:
      targets: ["github/*"]
audit:
  log: ".lorm/audit.jsonl"
  record_fields: [timestamp, capability, level, authorizer, action, params, diagnosis_ref, outcome, verified]
"""


def mcp_payload(tool, tool_input, project):
    return {"session_id": "test-session", "cwd": project,
            "hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": tool_input}


def test_mcp():
    print("MCP tools")
    p = make_project(MCP_L5)
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__query", {"query": "ANALYZE prod.orders"}, p), p)
    check("MCP valid L5 -> allow",
          d == "allow" and "mcp.postgres.analyze" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__query", {"query": "DROP TABLE prod.orders"}, p), p)
    check("MCP input pattern mismatch -> not the cap; read-verb query -> silent",
          d is None, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__execute", {"query": "ANALYZE x"}, p), p)
    check("MCP tool pattern mismatch + mutating verb -> builtin ask",
          d == "ask" and "mcp.write_operation" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__github__create_issue", {"title": "bug"}, p), p)
    check("MCP L4 entry -> ask", d == "ask" and "mcp.github.issue" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__github__get_issue", {"number": 1}, p), p)
    check("MCP read-only verb unlisted -> silent", d is None, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__slack__send_message", {"text": "hi"}, p), p)
    check("MCP mutating verb unlisted -> ask", d == "ask", f"{d} {r}")

    expired = MCP_L5.replace(f"expires: {FUTURE}", f"expires: {PAST}")
    p2 = make_project(expired)
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__query", {"query": "ANALYZE prod.orders"}, p2), p2)
    check("MCP expired L5 -> ask", d == "ask" and PAST in r, f"{d} {r}")

    p3 = make_project(MCP_L5)
    audit_seed(p3, "mcp.postgres.analyze", 3, age_seconds=60)
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__query", {"query": "ANALYZE prod.orders"}, p3), p3)
    check("MCP rate exhausted -> ask", d == "ask" and "3/3" in r, f"{d} {r}")

    # non-string input value matched via JSON serialization
    numeric = MCP_L5.replace('query: "ANALYZE *"', 'limit: "1*"')
    p4 = make_project(numeric)
    rc, d, r, _ = run_gate("pre", mcp_payload(
        "mcp__postgres__query", {"limit": 10}, p4), p4)
    check("MCP non-string input matched via JSON form", d == "allow", f"{d} {r}")

    # post: audit record for MCP execution
    p5 = make_project(MCP_L5)
    payload = mcp_payload("mcp__postgres__query",
                          {"query": "ANALYZE prod.orders"}, p5)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "ANALYZE"
    run_gate("post", payload, p5)
    audit = os.path.join(p5, ".lorm", "audit.jsonl")
    rec = json.loads(open(audit).read().splitlines()[0])
    check("MCP post record: L5 + policy authorizer + tool name in action",
          rec["level"] == "L5"
          and rec["authorizer"] == "policy:mcp.postgres.analyze@1"
          and "mcp__postgres__query" in rec["action"],
          str(rec))
    for x in (p, p2, p3, p4, p5):
        shutil.rmtree(x)


def with_conditions(conds_yaml):
    """BASE_L5 with a conditions block injected into fs.cleanup.build."""
    return BASE_L5.replace("    rollback:", conds_yaml + "    rollback:")


def test_executable_conditions():
    print("executable conditions (schema 1.3)")
    passing = with_conditions(
        "    conditions:\n"
        "      - text: \"build dir exists\"\n"
        "        check: \"test -d build\"\n")
    p = make_project(passing)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("passing check -> allow with check note",
          d == "allow" and "1 condition check(s) passed" in r, f"{d} {r}")

    failing = with_conditions(
        "    conditions:\n"
        "      - text: \"deploy lock absent\"\n"
        "        check: \"test ! -f deploy.lock\"\n")
    p2 = make_project(failing)
    open(os.path.join(p2, "deploy.lock"), "w").write("busy")
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p2), p2)
    check("failing check -> ask naming the condition",
          d == "ask" and "deploy lock absent" in r, f"{d} {r}")

    timing_out = with_conditions(
        "    conditions:\n"
        "      - text: \"slow probe\"\n"
        "        check: \"sleep 30\"\n"
        "        timeout: 1\n")
    p3 = make_project(timing_out)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p3), p3)
    check("check timeout -> ask", d == "ask" and "timed out" in r, f"{d} {r}")

    mixed = with_conditions(
        "    conditions:\n"
        "      - text: \"build dir exists\"\n"
        "        check: \"test -d build\"\n"
        "      - \"no other maintenance running\"\n")
    p4 = make_project(mixed)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p4), p4)
    check("mixed -> allow noting both kinds",
          d == "allow" and "1 condition check(s) passed" in r
          and "1 condition(s) remain agent-verified" in r, f"{d} {r}")

    soft_only = with_conditions(
        "    conditions:\n"
        "      - \"no other maintenance running\"\n")
    p5 = make_project(soft_only)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p5), p5)
    check("string-only conditions -> allow, agent-verified note",
          d == "allow" and "agent-verified (soft)" in r, f"{d} {r}")

    env_check = with_conditions(
        "    conditions:\n"
        "      - text: \"env vars provided\"\n"
        "        check: \"test \\\"$LORM_CAPABILITY\\\" = fs.cleanup.build"
        " -a -n \\\"$LORM_ACTION\\\"\"\n")
    p6 = make_project(env_check)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p6), p6)
    check("check sees LORM_* env vars", d == "allow", f"{d} {r}")
    for x in (p, p2, p3, p4, p5, p6):
        shutil.rmtree(x)


REVIEW = os.path.join(REPO, "skills", "lorm", "scripts", "lorm_review.py")


def run_review(project, *extra):
    proc = subprocess.run(
        [sys.executable, REVIEW, project, "--json", *extra],
        capture_output=True, text=True, timeout=30)
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def seed_records(project, records):
    os.makedirs(os.path.join(project, ".lorm"), exist_ok=True)
    with open(os.path.join(project, ".lorm", "audit.jsonl"), "a") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def ts_ago(**kw):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


def exec_rec(cap, ts, verified="pending", level="L4"):
    return {"timestamp": ts, "capability": cap, "level": level,
            "authorizer": "human:session t", "action": f"do {cap}",
            "params": {}, "diagnosis_ref": "t", "outcome": "ok",
            "verified": verified}


def test_review():
    print("trust-lifecycle review")
    # promotion candidate: 12 verified L4 executions, 0 failures
    p = make_project(L4_ENTRY)
    seed_records(p, [exec_rec("db.index.create", ts_ago(days=i + 1),
                              verified="verified") for i in range(12)])
    out = run_review(p)
    promos = out["findings"]["promotions"]
    check("12 verified -> promotion candidate",
          len(promos) == 1 and promos[0]["capability"] == "db.index.create",
          str(promos))
    check("draft has placeholders + inherited match/bounds",
          "DRAFT" in promos[0]["draft"]["policy"]["author"]
          and promos[0]["draft"]["match"].get("command_patterns"),
          str(promos[0]["draft"]))

    # below track threshold -> no proposal
    out = run_review(p, "--min-track", "20")
    check("track below threshold -> no promotion",
          not out["findings"]["promotions"], str(out["findings"]))

    # demotion: failed verification, no active demotion
    p2 = make_project(BASE_L5)
    seed_records(p2, [
        exec_rec("fs.cleanup.build", ts_ago(days=2), verified="verified",
                 level="L5"),
        exec_rec("fs.cleanup.build", ts_ago(days=1), verified="failed",
                 level="L5"),
    ])
    out = run_review(p2)
    dems = out["findings"]["demotions"]
    check("failed verification -> demotion proposal L5->L4",
          len(dems) == 1 and dems[0]["draft"]["to"] == "L4", str(dems))
    check("failing capability is not a promotion candidate",
          not out["findings"]["promotions"], "")

    # verification record joining: pending execution + skill verification
    p3 = make_project(L4_ENTRY)
    t = ts_ago(days=1)
    seed_records(p3, [exec_rec("db.index.create", t)])
    seed_records(p3, [{"timestamp": ts_ago(hours=23), "capability":
                       "db.index.create", "verified": "verified",
                       "x-verifies": t, "x-writer": "lorm-skill"}])
    out = run_review(p3)
    check("verification record joins execution",
          out["stats"]["db.index.create"]["verified"] == 1
          and out["stats"]["db.index.create"]["pending"] == 0,
          str(out["stats"]))

    # low verification coverage -> hygiene, not promotion
    p4 = make_project(L4_ENTRY)
    seed_records(p4, [exec_rec("db.index.create", ts_ago(days=i + 1))
                      for i in range(12)])
    out = run_review(p4)
    check("pending-heavy history -> hygiene finding, no promotion",
          not out["findings"]["promotions"]
          and any("coverage" in h["issue"] for h in out["findings"]["hygiene"]),
          str(out["findings"]))

    # expiry warning
    soon = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    p5 = make_project(BASE_L5.replace(f"expires: {FUTURE}", f"expires: {soon}"))
    out = run_review(p5)
    check("policy expiring soon -> expiry warning",
          any("expires in" in e["status"] for e in out["findings"]["expiry"]),
          str(out["findings"]["expiry"]))

    # old records outside window are ignored
    p6 = make_project(L4_ENTRY)
    seed_records(p6, [exec_rec("db.index.create", ts_ago(days=200),
                               verified="verified") for _ in range(12)])
    out = run_review(p6, "--window", "90")
    check("records outside window ignored", not out["stats"], str(out["stats"]))

    for x in (p, p2, p3, p4, p5, p6):
        shutil.rmtree(x)


def add_caps(base, caps_yaml):
    """Insert extra capability entries BEFORE the audit block."""
    return base.replace("audit:\n", caps_yaml + "audit:\n")


def test_multi_cap():
    print("multiple capabilities on one command")
    # equal specificity (identical patterns) -> tie -> most restrictive wins
    two = add_caps(BASE_L5, """\
  - id: fs.cleanup.strict
    level: L4
    match: {tools: [Bash], command_patterns: ["rm -rf build*"]}
    bounds: {targets: ["build/*"]}
""")
    p = make_project(two)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p), p)
    check("equal specificity tie -> ask wins", d == "ask", f"{d} {r}")
    shutil.rmtree(p)

    # broad L4 catch-all + narrow L5 exception -> specificity wins
    carveout = add_caps(BASE_L5, """\
  - id: fs.delete.docs
    level: L4
    match: {tools: [Bash], command_patterns: ["rm *"]}
    bounds: {targets: ["*"]}
""")
    p2 = make_project(carveout)
    rc, d, r, _ = run_gate("pre", bash_payload("rm -rf build", p2), p2)
    check("narrow L5 beats broad L4 catch-all (specificity)",
          d == "allow" and "fs.cleanup.build" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", bash_payload("rm data.txt", p2), p2)
    check("outside the carve-out -> broad L4 still asks",
          d == "ask" and "fs.delete.docs" in r, f"{d} {r}")
    shutil.rmtree(p2)


MECH_WRITE = """\
lorm_policy: "1.4"
metadata: {project: test, owner: owner@example.com}
defaults: {max_level: L3, unknown_action: escalate}
capabilities:
  - id: fs.write.notes
    level: L4
    match:
      tools: [Write, Edit]
      path_patterns: ["notes/*"]
    bounds: {targets: ["notes/*"]}
    verification:
      expect: "file written with the marker"
      mechanical:
        checks:
          - file_exists: "$TOOL_FILE"
          - file_contains: {path: "$TOOL_FILE", substring: "MARKER-OK"}
"""

MECH_BASH = """\
lorm_policy: "1.4"
metadata: {project: test, owner: owner@example.com}
defaults: {max_level: L3, unknown_action: escalate}
capabilities:
  - id: fs.cleanup.build
    level: L4
    match:
      tools: [Bash]
      command_patterns: ["rm -rf build*"]
    bounds: {targets: ["build/*"]}
    verification:
      expect: "clean exit"
      mechanical:
        checks:
          - exit_code: 0
          - output_contains: "removed"
"""

MECH_MALFORMED = """\
lorm_policy: "1.4"
metadata: {project: test, owner: owner@example.com}
defaults: {max_level: L3, unknown_action: escalate}
capabilities:
  - id: fs.cleanup.build
    level: L4
    match:
      tools: [Bash]
      command_patterns: ["rm -rf build*"]
    bounds: {targets: ["build/*"]}
    verification:
      expect: "whatever"
      mechanical:
        checks:
          - no_such_check: 42
"""


def test_mechanical_verification():
    print("mechanical verification (schema 1.4)")

    # Write path: file_exists + file_contains via $TOOL_FILE
    p = make_project(MECH_WRITE)
    os.makedirs(os.path.join(p, "notes"), exist_ok=True)
    target = os.path.join(p, "notes", "a.md")
    open(target, "w").write("hello MARKER-OK world")
    payload = write_payload("notes/a.md", p)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "File created successfully"
    rc, msg, err = run_gate_post(payload, p)
    audit = os.path.join(p, ".lorm", "audit.jsonl")
    rec = json.loads(open(audit).read().splitlines()[-1])
    check("write checks pass -> verified",
          rec["verified"] == "verified", str(rec) + err)
    check("verified record carries x-verified-by",
          rec.get("x-verified-by") == "lorm-hook-mechanical", str(rec))
    check("passing verification -> no systemMessage", msg is None, str(msg))

    # file_contains miss -> failed + detail names the check
    open(target, "w").write("marker is gone")
    rc, msg, err = run_gate_post(payload, p)
    rec = json.loads(open(audit).read().splitlines()[-1])
    check("file_contains miss -> failed",
          rec["verified"] == "failed", str(rec) + err)
    check("failure detail names the check",
          "file_contains" in rec.get("x-verify-detail", ""), str(rec))
    check("mechanical failure -> systemMessage names capability",
          msg is not None and "fs.write.notes" in msg, str(msg))
    shutil.rmtree(p)

    # Bash: exit_code + output_contains from a dict-shaped tool_response
    p2 = make_project(MECH_BASH)
    payload = bash_payload("rm -rf build", p2)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_response"] = {"stdout": "removed build/", "exit_code": 0}
    rc, msg, err = run_gate_post(payload, p2)
    audit2 = os.path.join(p2, ".lorm", "audit.jsonl")
    rec = json.loads(open(audit2).read().splitlines()[-1])
    check("bash dict response, exit 0 + output hit -> verified",
          rec["verified"] == "verified", str(rec) + err)

    # plain-string output: exit code unrecoverable -> pending (degradation)
    payload = bash_payload("rm -rf build", p2)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "removed build/"
    rc, msg, err = run_gate_post(payload, p2)
    rec = json.loads(open(audit2).read().splitlines()[-1])
    check("string output, no exit code -> stays pending",
          rec["verified"] == "pending" and "x-verified-by" not in rec,
          str(rec) + err)

    # output_contains miss -> failed
    payload = bash_payload("rm -rf build", p2)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_response"] = {"stdout": "nothing to do", "exit_code": 0}
    rc, msg, err = run_gate_post(payload, p2)
    rec = json.loads(open(audit2).read().splitlines()[-1])
    check("output_contains miss -> failed",
          rec["verified"] == "failed"
          and "output_contains" in rec.get("x-verify-detail", ""),
          str(rec) + err)

    # interrupted response counts as nonzero exit -> failed
    payload = bash_payload("rm -rf build", p2)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_response"] = {"stdout": "removed build/", "interrupted": True}
    rc, msg, err = run_gate_post(payload, p2)
    rec = json.loads(open(audit2).read().splitlines()[-1])
    check("interrupted -> exit_code check failed",
          rec["verified"] == "failed"
          and "exit_code" in rec.get("x-verify-detail", ""),
          str(rec) + err)
    shutil.rmtree(p2)

    # malformed mechanical block -> pending, exit 0, never crashes
    p3 = make_project(MECH_MALFORMED)
    payload = bash_payload("rm -rf build", p3)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_response"] = {"stdout": "removed", "exit_code": 0}
    rc, msg, err = run_gate_post(payload, p3)
    rec = json.loads(open(os.path.join(p3, ".lorm", "audit.jsonl"))
                     .read().splitlines()[-1])
    check("malformed mechanical block -> pending, exit 0",
          rc == 0 and rec["verified"] == "pending", f"rc={rc} {rec} {err}")
    shutil.rmtree(p3)

    # pending backlog threshold: 9 seeded + 1 new = 10 -> message; 11 -> none
    p4 = make_project(BASE_L5)
    ts = (datetime.datetime.now(datetime.timezone.utc)
          - datetime.timedelta(seconds=120))
    os.makedirs(os.path.join(p4, ".lorm"), exist_ok=True)
    with open(os.path.join(p4, ".lorm", "audit.jsonl"), "a") as fh:
        for _ in range(9):
            fh.write(json.dumps({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "capability": "fs.cleanup.build", "level": "L5",
                "authorizer": "policy:x@1", "action": "rm -rf build",
                "params": {}, "diagnosis_ref": "t", "outcome": "ok",
                "verified": "pending"}) + "\n")
    payload = bash_payload("rm -rf build", p4)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "removed"
    rc, msg, err = run_gate_post(payload, p4)
    check("pending backlog hits 10 -> systemMessage",
          msg is not None and "10" in msg and "fs.cleanup.build" in msg,
          f"{msg} {err}")
    rc, msg, err = run_gate_post(payload, p4)
    check("11th pending -> no message (exact thresholds only)",
          msg is None, str(msg))
    shutil.rmtree(p4)


DISCOVER = os.path.join(REPO, "skills", "lorm", "scripts", "lorm_discover.py")


def read_observations(project):
    path = os.path.join(project, ".lorm", "observations.jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path).read().splitlines() if l.strip()]


def post(command_or_path, project, tool="Bash"):
    if tool == "Bash":
        payload = bash_payload(command_or_path, project)
    else:
        payload = write_payload(command_or_path, project, tool=tool)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "ok"
    return run_gate_post(payload, project)


def test_observations():
    print("observations log (unclassified actions)")
    p = make_project(BASE_L5)
    audit = os.path.join(p, ".lorm", "audit.jsonl")

    # unmatched benign Bash -> observation, no audit record
    rc, msg, err = post("git status", p)
    obs = read_observations(p)
    check("unmatched bash -> observation with skeleton",
          len(obs) == 1 and obs[0]["tool"] == "Bash"
          and obs[0]["skeleton"] == "git status", f"{obs} {err}")
    check("unmatched bash -> no audit record", not os.path.exists(audit), "")

    # skeleton stability: differing literals cluster to one shape
    post('git commit -m "first message"', p)
    post('git commit -m "a totally different one"', p)
    obs = read_observations(p)
    skels = [o["skeleton"] for o in obs[-2:]]
    check("differing literals -> identical skeletons",
          skels[0] == skels[1] == "git commit -m «ARG»", str(skels))

    # matched capability -> audit record, no observation
    n_before = len(read_observations(p))
    post("rm -rf build", p)
    check("matched call -> audit record, no observation",
          os.path.exists(audit) and len(read_observations(p)) == n_before, "")

    # classifier hit -> audit record, no observation
    post("rm data.txt", p)
    check("classifier hit -> audit record, no observation",
          len(open(audit).read().splitlines()) == 2
          and len(read_observations(p)) == n_before, "")

    # in-project Write -> path skeleton
    os.makedirs(os.path.join(p, "src"), exist_ok=True)
    post("src/x.py", p, tool="Write")
    obs = read_observations(p)
    check("in-project write -> dir/*.ext skeleton",
          obs[-1]["tool"] == "Write" and obs[-1]["skeleton"] == "src/*.py",
          str(obs[-1]))

    # self-noise: commands touching .lorm/ or the policy file are not signal
    n_before = len(read_observations(p))
    post("cat .lorm/audit.jsonl", p)
    post("cat lorm-policy.yaml", p)
    check(".lorm/policy traffic -> no observation",
          len(read_observations(p)) == n_before, "")

    # MCP read-only unlisted tool -> field-name skeleton
    payload = {"session_id": "test-session", "cwd": p,
               "hook_event_name": "PostToolUse",
               "tool_name": "mcp__github__get_issue",
               "tool_input": {"repo": "a/b", "number": 7},
               "tool_output": "ok"}
    run_gate_post(payload, p)
    obs = read_observations(p)
    check("unlisted MCP tool -> name+field skeleton",
          obs[-1]["skeleton"] == "mcp__github__get_issue(number,repo)",
          str(obs[-1]))
    shutil.rmtree(p)

    # no policy file -> no observations at all
    p2 = make_project(None)
    post("git status", p2)
    check("no policy -> no observations", read_observations(p2) == [], "")
    shutil.rmtree(p2)

    # size cap: oversized log is halved before append, newest kept
    p3 = make_project(BASE_L5)
    obs_path = os.path.join(p3, ".lorm", "observations.jsonl")
    os.makedirs(os.path.dirname(obs_path), exist_ok=True)
    filler = {"timestamp": "2026-01-01T00:00:00Z", "tool": "Bash",
              "skeleton": "filler " + "x" * 100, "x-session": "old"}
    line = json.dumps(filler, ensure_ascii=False)
    n_lines = (600 * 1024) // (len(line) + 1)
    with open(obs_path, "w") as fh:
        for _ in range(n_lines):
            fh.write(line + "\n")
    post("git status", p3)
    lines = open(obs_path).read().splitlines()
    check("oversized log halved, newest appended",
          len(lines) <= n_lines // 2 + 2
          and json.loads(lines[-1])["skeleton"] == "git status",
          f"{n_lines} -> {len(lines)}")
    shutil.rmtree(p3)


def seed_observations(project, rows):
    os.makedirs(os.path.join(project, ".lorm"), exist_ok=True)
    with open(os.path.join(project, ".lorm", "observations.jsonl"), "a") as fh:
        for tool, skeleton, age_days, session in rows:
            ts = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=age_days))
            fh.write(json.dumps({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tool": tool, "skeleton": skeleton,
                "x-session": session}) + "\n")


def run_discover(project, *extra):
    proc = subprocess.run(
        [sys.executable, DISCOVER, project, "--json", *extra],
        capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return None, proc.stderr
    return json.loads(proc.stdout), proc.stderr


def test_discover():
    print("discovery analyzer")
    p = make_project(BASE_L5)
    seed_observations(p, [
        *[("Bash", "git commit -m «ARG»", 1, f"s{i % 3}") for i in range(6)],
        ("Bash", "curl -s «ARG»", 2, "s1"),
        ("Bash", "curl -s «ARG»", 3, "s1"),
        *[("Bash", "make «ARG»", 90, "s1") for _ in range(5)],
        *[("Write", "src/*.py", 1, "s1") for _ in range(3)],
        *[("Edit", "src/*.py", 2, "s2") for _ in range(3)],
    ])
    out, err = run_discover(p)
    check("discover runs", out is not None, err)
    props = {tuple(c["tools"]): c for c in out["proposals"]}
    git = props.get(("Bash",))
    check("cluster above threshold -> proposal (out-of-window ignored)",
          git is not None and git["skeleton"] == "git commit -m «ARG»"
          and git["count"] == 6, str(list(props)))
    check("draft: L3, derived pattern, both notes",
          git["draft"]["level"] == "L3"
          and git["draft"]["match"]["command_patterns"] == ["git commit -m *"]
          and "VERIFICATION GAP" in git["draft"]["x-note-verification"]
          and "DENY" in git["draft"]["x-note-level"], str(git["draft"]))
    check("draft id derived from skeleton",
          git["draft"]["id"] == "cmd.git.commit", git["draft"]["id"])
    we = props.get(("Edit", "Write"))
    check("Write+Edit same skeleton merge into one cluster",
          we is not None and we["count"] == 6
          and we["draft"]["match"]["path_patterns"] == ["src/*.py"],
          str(list(props)))
    check("session spread counted", git["sessions"] == 3, str(git))

    out, _ = run_discover(p, "--min-count", "10")
    check("--min-count respected", out["proposals"] == [], str(out["proposals"]))
    out, _ = run_discover(p, "--window", "365", "--min-count", "5")
    counts = {c["skeleton"]: c["count"] for c in out["proposals"]}
    check("--window widens: old cluster appears",
          counts.get("make «ARG»") == 5, str(counts))
    shutil.rmtree(p)


def test_outside_project_match():
    print("outside-project match (schema 1.5)")
    # An outside directory we grant an L5 capability to write into, plus a
    # sibling outside path the grant does NOT cover.
    outside_dir = tempfile.mkdtemp(prefix="lorm-outside-")
    target_in = os.path.join(outside_dir, "note.md")
    target_out = os.path.join(tempfile.gettempdir(), "lorm-ungranted.md")

    outside_l5 = f"""\
lorm_policy: "1.5"
metadata: {{project: test, owner: owner@example.com}}
defaults: {{max_level: L3, unknown_action: escalate}}
capabilities:
  - id: fs.write.secondbrain
    level: L5
    match:
      tools: [Write, Edit]
      path_outside_project: true
    policy:
      version: 1
      author: author@example.com
      approved_by: approver@example.com
      approved_at: 2026-07-01
      expires: {FUTURE}
      tested: "test corpus"
    bounds:
      targets: ["{outside_dir}/*"]
    rollback: "revert"
    verification:
      expect: "written"
      mechanical:
        checks:
          - file_exists: "$TOOL_FILE"
audit:
  log: ".lorm/audit.jsonl"
  record_fields: [timestamp, capability, level, authorizer, action, params, diagnosis_ref, outcome, verified]
"""
    # L5 flag entry, absolute targets: within scope -> allow, beyond -> degrade
    p = make_project(outside_l5)
    rc, d, r, _ = run_gate("pre", write_payload(target_in, p), p)
    check("outside write within absolute targets -> allow",
          d == "allow" and "fs.write.secondbrain" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre", write_payload(target_out, p), p)
    check("outside write beyond targets -> ask (degrade to L4)",
          d == "ask" and "outside" in r and "fs.write.secondbrain" in r, f"{d} {r}")
    rc, d, r, _ = run_gate("pre",
                           write_payload(target_in, p, tool="Edit"), p)
    check("Edit also covered by the flag -> allow", d == "allow", f"{d} {r}")

    # L4 / L3 flag entries gate as usual
    p2 = make_project(outside_l5.replace("level: L5", "level: L4"))
    rc, d, r, _ = run_gate("pre", write_payload(target_in, p2), p2)
    check("outside write, L4 flag entry -> ask",
          d == "ask" and "fs.write.secondbrain" in r, f"{d} {r}")
    p3 = make_project(outside_l5.replace("level: L5", "level: L3"))
    rc, d, r, _ = run_gate("pre", write_payload(target_in, p3), p3)
    check("outside write, L3 flag entry -> deny",
          d == "deny" and "fs.write.secondbrain" in r, f"{d} {r}")

    # Regression: no flag entry -> the built-in classifier still fires
    p4 = make_project(ESCALATE_DEFAULTS)
    rc, d, r, _ = run_gate("pre", write_payload(target_in, p4), p4)
    check("no flag entry -> classifier fallback ask",
          d == "ask" and "outside_project" in r, f"{d} {r}")
    # Regression: an in-project write is unaffected by the flag entry
    rc, d, r, _ = run_gate("pre",
                           write_payload(os.path.join(p, "notes.md"), p), p)
    check("in-project write with flag-only entry -> silent (no path match)",
          d is None, f"{d} {r}")

    # Post: attribution flips to the policy entry and mechanical verification
    # now runs for this class (previously impossible via the classifier).
    p5 = make_project(outside_l5)
    open(target_in, "w").write("hi")
    payload = write_payload(target_in, p5)
    payload["hook_event_name"] = "PostToolUse"
    payload["tool_output"] = "File created successfully"
    rc, msg, err = run_gate_post(payload, p5)
    audit = os.path.join(p5, ".lorm", "audit.jsonl")
    rec = json.loads(open(audit).read().splitlines()[-1])
    check("post: attributed to policy entry, not classifier",
          rec["capability"] == "fs.write.secondbrain"
          and rec["authorizer"].startswith("policy:fs.write.secondbrain@"),
          str(rec) + err)
    check("post: mechanical verification runs for outside-project write",
          rec["verified"] == "verified", str(rec) + err)

    for x in (p, p2, p3, p4, p5, outside_dir):
        shutil.rmtree(x, ignore_errors=True)
    if os.path.exists(target_out):
        os.remove(target_out)


def main():
    for fn in (test_passive, test_l5_allow_and_degrades, test_rate_limit,
               test_l4_l3_and_defaults, test_compound_and_wrappers,
               test_write_paths, test_self_protection, test_fail_closed,
               test_hook_active_marker, test_post_audit, test_mcp,
               test_executable_conditions,
               test_review, test_multi_cap, test_mechanical_verification,
               test_observations, test_discover, test_outside_project_match):
        fn()
    print(f"\n{PASS} passed, {len(FAIL)} failed")
    if FAIL:
        print("failed:", *FAIL, sep="\n  - ")
        sys.exit(1)


if __name__ == "__main__":
    main()
