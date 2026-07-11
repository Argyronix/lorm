# LORM Hard Enforcement — the Claude Code Plugin

*Normative for the enforcement hook. The policy format itself is defined by
SPEC.md §13 and `schema/lorm-policy.schema.json`.*

The plugin wires two hooks around every `Bash`, `Write`, `Edit`, and MCP
(`mcp__*`) tool call:

- **PreToolUse** (`hooks/scripts/lorm_gate.py pre`) — the authorization
  gate: `allow` what a valid L5 policy entry proves, force `ask` where LORM
  demands a human, `deny` what the policy forbids.
- **PostToolUse** (`lorm_gate.py post`) — the audit writer: appends SPEC
  §10.3 execution records to the audit log that rate limits are counted
  against, and maintains the `.lorm/hook-active` marker for skill
  coexistence.

## Install

```bash
# local (development)
claude --plugin-dir /path/to/lorm

# from GitHub
/plugin marketplace add Argyronix/lorm
/plugin install lorm@argyronix-lorm
```

The plugin also ships the LORM agent skill (`skills/lorm/`) — one install
provides both the soft layer (agent discipline: diagnostics, uncertainty,
proposal blocks, conditions[]) and the hard layer (deterministic gating).
If you previously copied the skill into `.claude/skills/` manually, remove
that copy to avoid loading it twice.

**Without a `lorm-policy.yaml` in the project, the hooks are passive** —
they emit no opinion and Claude Code's normal permission flow applies
unchanged. Hard enforcement switches on when a policy file appears.

## Threat model — read this first

Silent pass-through is never "auto-run": when the gate has no opinion, the
call lands in Claude Code's own permission system, which in interactive
mode is itself a human gate. Classification gaps — obfuscated commands,
`bash -c`, `eval`, command substitution — therefore degrade to *normal
Claude Code behavior*, never to silent autonomy. Common indirection is
still caught (`eval`, `bash -c`, bare `sh` as a pipe target, `curl | sh`
route to `shell.indirect_exec`), but the plugin does not claim to defeat a
deliberately adversarial model; it makes an honest agent's authorization
boundary deterministic, auditable, and independent of the model's mood.

What the hook deterministically enforces: policy matching, L5 structural
validity (expiry, author≠approver), demotions, target bounds for file
paths, rate limits against the audit log, executable condition checks
(schema 1.3), policy-file and audit-log self-protection. What stays with
the skill (soft): plain-string `conditions[]`, `max_objects`, diagnosis
quality, outcome verification.

One consequence of executable checks deserves a line in the threat model:
`conditions[].check` commands come from the policy file, which is
human-approved and P1-protected — the hook itself gates agent attempts to
edit it. A check runs with the same privileges the gated action would
have; treat writing checks with the same care as writing the policy.

## Decision table (PreToolUse)

Combining rule when several segments/capabilities produce decisions:
**deny > ask > allow > no-opinion.**

| # | Condition | Output |
|---|---|---|
| 0 | no policy file | silent (passive) |
| 1 | policy unreadable / parse error | `ask` — "policy present but unusable" |
| 2 | `.yaml` policy and PyYAML missing | `ask` — install pyyaml or use `lorm-policy.json` |
| P1 | Write/Edit/Bash-rewrite targeting the policy file | `ask` (overrides any allow) — SPEC I-8 |
| P2 | truncate/delete/rewrite of the audit log (`>>` append exempt) | `deny` — SPEC I-6 |
| 3 | matched L5, structurally valid, in targets, rate OK | **`allow`** citing policy id@version, expiry, rate n/max |
| 4 | matched L5, any check fails (expired, demoted, structural, rate, targets, corrupt log) | `ask` naming the failed check (SPEC 13-1) |
| 5 | matched effective L4 | `ask` — fires even in acceptEdits/bypassPermissions modes |
| 6 | matched effective ≤ L3 | `deny` — recommend-only |
| 7 | built-in classifier hit, `defaults.unknown_action: refuse` | `deny` |
| 8 | built-in classifier hit, `escalate` or unset | `ask` with the classifier id; approving the dialog is the L4 authorization |
| 9 | nothing matched | silent → normal permission flow |
| 10 | internal engine error | `ask` with the error (fail-closed, never crash-open) |

## Matching semantics

- **Bash commands** are tokenized (`shlex`, shell punctuation) and split
  into segments on `&& || ; | &` and newlines; leading wrappers
  (`sudo`, `env VAR=...`, `nohup`, `time`, `command`, `exec`) are stripped.
  **Each segment is evaluated independently** — capabilities first, then
  built-in classifiers for segments no capability covers — so an
  L5-allowed segment can never smuggle a dangerous sibling through. An
  unparseable command falls back to matching the raw string.
- **Capability matching** uses the schema 1.1 `match` block:
  `command_patterns` (fnmatch vs segment text) for Bash,
  `path_patterns` (fnmatch vs project-relative path) for Write/Edit.
  Entries without `match` are **soft-only** — the hook ignores them.
  For command-shaped capabilities, `command_patterns` MUST encode the
  target scope (e.g. `"redis-cli -h session-cache FLUSHDB*"`, never
  `"redis-cli *"`) — Bash `bounds.targets` are not hook-verifiable.
- **Paths**: Write/Edit `file_path` is resolved to a real path (symlinks
  and `..` collapsed) relative to the project root; paths resolving
  outside the project hit the `fs.write.outside_project` built-in. Glob
  semantics are `fnmatch`: **`*` matches across `/`** (`build/*` covers
  the whole subtree); a pattern starting with `/` matches the absolute
  path; a path that is an ancestor of a target scope is within scope
  (deleting `build` is within `build/*`).
- **Rate limits**: sliding 3600-second window over execution records in
  the audit log. Missing log = zero prior actions; unparseable log =
  `ask`. Rotate the log by moving it aside (rotated files are not
  counted); never truncate it in place (P2 denies that anyway).
- **Built-in classifiers** live in `hooks/classifiers.json` (first match
  wins, order matters): `fs.delete`, `git.history.rewrite`, `git.push`,
  `db.destructive`, `sys.config.change`, `pkg.install`,
  `shell.indirect_exec`, `fs.write.outside_project`,
  `mcp.write_operation`. A policy overrides a built-in by listing a
  capability whose `match` covers the command or tool.

## MCP tools (schema 1.2)

MCP tool names map to action classes as `mcp__<server>__<tool>` →
`mcp.<server>.<tool>`. Matching uses two schema 1.2 `match` fields:

- `tool_patterns` — fnmatch against the full tool name
  (`mcp__postgres__query`). Never grant L4/L5 on a bare `mcp__*`.
- `input_patterns` — per-field fnmatch against `tool_input`; every listed
  field must exist and match (AND). Non-string values are matched against
  their JSON serialization. **This is where an MCP capability's target
  scope lives** — `bounds.targets` are not hook-verifiable for MCP, same
  as for Bash.

```yaml
match:
  tool_patterns: ["mcp__postgres__query"]
  input_patterns:
    query: "ANALYZE *"
```

Unlisted MCP tools with mutating-verb names (`create/delete/update/execute/
push/send/...` — see `mcp.write_operation` in classifiers.json) route
through `defaults.unknown_action`; read-only-verb tools (`get/list/read/
search`) pass silently to the normal permission flow. Known limitations:
self-protection (P1/P2) cannot see policy-file writes made through an MCP
filesystem server, and an input-pattern mismatch means "not this
capability", falling through to the classifier — encode broad enough
`input_patterns` deliberately.

## Executable conditions (schema 1.3)

`conditions[]` entries may be objects with a `check` command:

```yaml
conditions:
  - text: "no deployment in progress"
    check: "test ! -f /var/run/deploy.lock"
    timeout: 2                     # seconds, default 5, max 8
  - "cache hit rate < 20% sustained 15m"   # plain string: agent-verified
```

The hook runs each `check` from the project root with `LORM_CAPABILITY`,
`LORM_TOOL_NAME`, `LORM_ACTION`, and `CLAUDE_PROJECT_DIR` in the
environment. Exit 0 = the condition holds; a non-zero exit, a timeout, or
an exhausted overall budget (8 s across all checks, inside the 10 s hook
timeout) degrades the action to L4 with the condition named in the reason.
Checks run only after the cheaper validity checks (expiry, demotion,
targets, rate) have passed. Plain-string conditions remain the skill's
duty and are noted as such in the `allow` reason.

## Non-interactive mode (`claude -p`)

`ask` cannot be answered headlessly, so the call is not executed and the
model is told why. This is LORM-correct by construction: no human present
⇒ no L4 authorizer ⇒ no execution; only valid L5 policy entries act
autonomously. If you need headless execution of a recurring action class,
the honest fix is an L5 policy entry (SPEC §11) — or a programmatic
approver via `--permission-prompt-tool`.

## Audit records and the skill

PostToolUse appends one execution record per gated call that matched a
capability or classifier (`x-writer: "lorm-hook"`, `verified: "pending"`,
`diagnosis_ref: "unavailable-to-hook"` — the hook cannot see the model's
reasoning). The skill then appends *verification records* (`x-verifies`)
after checking outcomes; see `skills/lorm/references/policy-format.md`.
Records for actions the hook could not attribute to a valid L5 entry are
written as `level: "L4", authorizer: "human:session <id>"` — if it
executed, a human approved it.

## Testing

```bash
python3 tests/run_tests.py     # 46 assertions across ~10 scenario groups
```

Live smoke test: create a scratch project with a `defaults.unknown_action:
refuse` policy, run `claude --plugin-dir /path/to/lorm -p "delete x.txt
with rm"`, and confirm the deny reason in the output; switch to a valid L5
policy entry matching the command and confirm it runs without a prompt.
