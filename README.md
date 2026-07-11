# LORM — Layered Operational Responsibility Model

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
| [`SPEC.md`](SPEC.md) | The normative specification (RFC 2119 language) |
| [`RATIONALE.md`](RATIONALE.md) | Why the model exists — the non-normative argument |
| [`docs/related-work.md`](docs/related-work.md) | Positioning vs. Parasuraman–Sheridan–Wickens, SAE J3016, TM Forum Autonomous Networks, IBM autonomic computing |
| [`schema/lorm-policy.schema.json`](schema/lorm-policy.schema.json) | JSON Schema for the policy file, with [examples](schema/examples/) |
| [`skills/lorm/`](skills/lorm/) | The Agent Skill — LORM as agent discipline (soft enforcement) |
| [`hooks/`](hooks/) + [`docs/hard-enforcement.md`](docs/hard-enforcement.md) | PreToolUse authorization gate + PostToolUse audit trail (hard enforcement) |
| [`examples/`](examples/) | The model applied to [database operations](examples/database-operations.md), [coding agents](examples/coding-agent.md), [security ops](examples/cybersecurity.md) |

## Quick start

**1. Read the spec.** [`SPEC.md`](SPEC.md) — §2 (levels), §5 (invariants),
and §6 (trust lifecycle) are the core.

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

- Specification 2.0.0, the agent skill, and the enforcement plugin
  (PreToolUse gate + PostToolUse audit, policy schema 1.1 `match` blocks):
  **this repository, working and tested**.
- The skill alone is *soft* enforcement (disciplined agent behavior); the
  plugin's hooks make the authorization boundary deterministic. Neither
  claims to defeat a deliberately adversarial model — see the threat model
  in [`docs/hard-enforcement.md`](docs/hard-enforcement.md).
- Next: MCP tool coverage, project-level classifier extensions, structured
  machine-evaluable `conditions`.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
