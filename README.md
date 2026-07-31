# LORM — Layered Operational Responsibility Model

[![tests](https://github.com/Argyronix/lorm/actions/workflows/tests.yml/badge.svg)](https://github.com/Argyronix/lorm/actions/workflows/tests.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21723237.svg)](https://doi.org/10.5281/zenodo.21723237)

LORM defines six levels of operational responsibility (L0–L5) for systems
that participate in operational decisions — AI agents, automation platforms,
control loops. Unlike capability-graded autonomy scales (SAE, most AI-agent
taxonomies), LORM grades one thing:

> **Who authorized the action** — nobody needed (observing, explaining),
> a human per action, or an explicit, versioned, expiring policy.

| Level | Name | The system may… | Authorized by |
| :-: | --- | --- | --- |
| L0 | Structural Awareness | know what exists | — |
| L1 | Behavioral Observation | observe what is happening | — |
| L2 | Diagnostics & Explanation | explain why (with stated uncertainty) | — |
| L3 | Recommendation | propose actions; never execute | human decides |
| L4 | Controlled Execution | execute one approved action in bounds | human, per action |
| L5 | Policy-Driven Autonomy | execute without per-action approval | policy |

Levels attach to **capabilities** (action classes), never to systems. A
capability *earns* promotion on measured outcomes and is *automatically
demoted* on incidents, rollbacks, verification failures, telemetry loss, or
policy expiry. Delegation lives in a machine-readable policy file with a
mandatory expiry and a separated author/approver.

## What's in this repository

This repository is also a **Claude Code plugin**: one install provides the
agent skill (soft layer) and enforcement hooks (hard layer).

| Path | What it is |
| --- | --- |
| [`docs/user-guide.md`](docs/user-guide.md) | **Start here** — plain-language guide: scenarios, example configs, FAQ |
| [`SPEC.md`](SPEC.md) | The normative specification (RFC 2119 language) |
| [`RATIONALE.md`](RATIONALE.md) | Why the model exists — the non-normative argument |
| [`docs/related-work.md`](docs/related-work.md) | Positioning vs. Parasuraman–Sheridan–Wickens, SAE J3016, TM Forum Autonomous Networks, IBM autonomic computing |
| [`schema/lorm-policy.schema.json`](schema/lorm-policy.schema.json) | JSON Schema for the policy file, with [examples](schema/examples/) |
| [`skills/lorm/`](skills/lorm/) | The Agent Skill — LORM as agent discipline (soft enforcement) |
| [`hooks/`](hooks/) + [`docs/hard-enforcement.md`](docs/hard-enforcement.md) | PreToolUse authorization gate + PostToolUse audit trail (hard enforcement) |
| [`examples/`](examples/) | The model applied to [database operations](examples/database-operations.md), [coding agents](examples/coding-agent.md), [security ops](examples/cybersecurity.md) |

## Quick start

**1. Read.** New to LORM? Start with the
[user guide](docs/user-guide.md). For the normative core, read
[`SPEC.md`](SPEC.md) — §2 (levels), §5 (invariants), §6 (trust lifecycle).

**2. Install** — either the full plugin (recommended: skill + hooks):

```bash
claude --plugin-dir /path/to/lorm        # local
# or from GitHub:
/plugin marketplace add Argyronix/lorm
/plugin install lorm@argyronix-lorm
```

…or just the skill, copied into one project (soft layer only):

```bash
cp -r skills/lorm /path/to/project/.claude/skills/lorm
```

Pick one — installing the plugin *and* keeping a copied skill loads it
twice. The agent will classify every state-changing action by LORM level,
perform diagnostics before proposing, present structured approval requests
at L4, and execute autonomously only what a valid policy grants. With the
plugin, the hooks additionally make that boundary deterministic: valid L5
entries skip the permission prompt, L4-classified actions force it (even in
permissive modes), forbidden actions are denied, and every gated execution
lands in the audit log. Without a policy file the hooks are passive — see
[`docs/hard-enforcement.md`](docs/hard-enforcement.md).

**3. Write a policy** (optional — without one, everything state-changing is
L4). Start from
[`schema/examples/minimal.lorm-policy.yaml`](schema/examples/minimal.lorm-policy.yaml),
grow toward
[`full.lorm-policy.yaml`](schema/examples/full.lorm-policy.yaml). Validate:

```bash
python3 skills/lorm/scripts/validate_policy.py lorm-policy.yaml
```

## What the hook decides

With [`schema/examples/full.lorm-policy.yaml`](schema/examples/full.lorm-policy.yaml)
in place as the project's `lorm-policy.yaml`, every state-changing action gets one
of these answers *before* it runs. The decisions and reason strings below are what
the gate returns — copied from a run, not paraphrased:

| Action | Decision | Reason returned by the gate |
| --- | :-: | --- |
| `redis-cli -h session-cache FLUSHDB` | `allow` | authorized by policy `cache.flush` v3 (expires 2026-10-01); rate 0/2 this hour; 1 condition check(s) passed, 1 condition(s) remain agent-verified |
| `psql -c "CREATE INDEX CONCURRENTLY …"` | `ask` | LORM L4: `db.index.create` requires per-action human authorization |
| `psql -c "DROP INDEX idx_orders"` | `deny` | policy caps `db.index.drop` at L3 (listed as recommend-only); propose, don't execute (SPEC 2.5) |
| `rm -rf build` | `ask` | unlisted `fs.delete`-class action (defaults.max_level=L3) — approving this dialog is the L4 human authorization (SPEC L4-1) |
| `redis-cli -h session-cache FLUSHDB && rm -rf /` | `ask` | unlisted `fs.delete`-class action (defaults.max_level=L3) — approving this dialog is the L4 human authorization (SPEC L4-1) |

`allow` runs without a prompt. `ask` becomes Claude Code's permission dialog — even
in permissive modes, which is the point: an L4 action cannot be auto-approved away.
`deny` blocks the call and tells the agent to propose instead.

The last row is the per-segment rule: the first segment is granted at L5 on its own,
but the sibling is not, and the most restrictive decision wins — so an authorized
command cannot smuggle an unauthorized one alongside it.

The gate speaks JSON (`hookSpecificOutput.permissionDecision` plus
`permissionDecisionReason`); Claude Code renders it. Reproduce any row with:

```bash
cp schema/examples/full.lorm-policy.yaml /path/to/project/lorm-policy.yaml
```

Every gated execution then appends one record to `.lorm/audit.jsonl` — two real
records, with the routine fields (`params`, `outcome`, `diagnosis_ref`, `x-writer`,
`x-session`) dropped here for width:

```json
{"timestamp": "2026-07-30T12:56:53Z", "capability": "fs.write.migrations",
 "level": "L4", "authorizer": "human:session s1",
 "action": "Write migrations/003_add_index.sql", "verified": "verified",
 "x-verified-by": "lorm-hook-mechanical",
 "x-verify-detail": "2 mechanical check(s) passed"}

{"timestamp": "2026-07-30T12:56:53Z", "capability": "cache.flush",
 "level": "L5", "authorizer": "policy:cache.flush@3",
 "action": "redis-cli -h session-cache FLUSHDB", "verified": "pending"}
```

`authorizer` is the whole distinction between the two authority levels: a human for
the L4 action, a named policy version for the L5 one. The first record was verified
mechanically by the hook (schema 1.4 `verification.mechanical`); the second has no
mechanical check declared, so it stays `pending` until verified — and a capability
that accumulates executions with nothing verified is a stalled trust lifecycle, which
`/lorm:lorm-review` reports on.

## Design commitments

- **Propose, never enact** — the system may draft policy changes; only
  humans activate them.
- **Promotion is slow and human-gated; demotion is fast and automatic.**
- **No immortal policies** — every L5 grant expires.
- **Unverifiable actions never reach L5** — if the outcome can't be checked,
  a human stays in the loop.
- **Approval fatigue is a named failure mode**, and the honest fix is
  either fewer, richer approvals — or one deliberate policy. Never a ritual.

## Status and roadmap

- Specification 2.0.2, the agent skill, and the enforcement plugin 2.7.0
  (PreToolUse gate + PostToolUse audit, policy schema 1.5):
  **this repository, working and tested** — 113 tests, run in CI on Python
  3.10 through 3.14. The engine needs the standard library and nothing else;
  PyYAML is required only to read YAML policy files, and CI proves a JSON
  policy is enforced without it. `validate_policy.py` additionally needs
  `jsonschema`.
- What CI cannot cover: whether Claude Code itself wires the hooks and loads
  the plugin correctly. That is verified by hand
  (`claude --plugin-dir . -p "…"`), and the 2.4.1 fix — a duplicate hooks
  load on marketplace install — is the kind of defect only that catches.
- The skill alone is *soft* enforcement (disciplined agent behavior); the
  plugin's hooks make the authorization boundary deterministic. Neither
  claims to defeat a deliberately adversarial model — see the threat model
  in [`docs/hard-enforcement.md`](docs/hard-enforcement.md).
- MCP tools are gated since 2.2.0 (schema 1.2 `tool_patterns` /
  `input_patterns`).
- Trust-lifecycle tooling since 2.3.0: `/lorm:lorm-review` analyzes the
  audit log and drafts promotion/demotion transitions for human decision —
  see [`docs/trust-lifecycle.md`](docs/trust-lifecycle.md).
- Executable conditions since 2.4.0 (schema 1.3 `conditions[].check`) —
  the L5 allow path is fully deterministic when policies use them.
- Mechanical verification since 2.5.0 (schema 1.4
  `verification.mechanical`): where a success criterion is checkable right
  after the call, the hook writes the audit record `verified` or `failed`
  itself, with no agent step — and a failed verification is a demotion
  trigger.
- Discovery since 2.6.0: state-changing actions no policy entry claims are
  logged passively to `.lorm/observations.jsonl`, and the analyzer drafts
  policy entries for the recurring ones — so a gap in the policy surfaces
  as a proposal instead of silence.
- Outside-project writes since 2.7.0 (schema 1.5
  `match.path_outside_project`): a path with no project-relative form can
  now be claimed by policy, which puts that class on the trust lifecycle
  like any other instead of leaving it permanently outside it.
- Next: project-level classifier extensions.

The full version history is in [`CHANGELOG.md`](CHANGELOG.md). Design records
for the three most recent features — written as issue drafts before
implementation, retained afterwards — are in
[`docs/`](docs/) (`draft-issue-*.md`).

## Contributing

Pull requests are welcome in `hooks/`, `tests/`, `docs/` and `examples/`.
Changes to `SPEC.md` start as an issue, because a change to normative text is a
change to what the model means. The design invariants a pull request must not
break, the checks to run, and why there is no contributor licence agreement are
all in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Citing

Cite the specification version you worked from — see
[`CITATION.cff`](CITATION.cff), or use the "Cite this repository" button on
GitHub. Releases are archived on Zenodo:
[10.5281/zenodo.21723237](https://doi.org/10.5281/zenodo.21723237) always
resolves to the newest archived release, and each release also has its own DOI
if you need to pin one.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
