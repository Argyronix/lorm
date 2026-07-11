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

| Path | What it is |
| --- | --- |
| [`SPEC.md`](SPEC.md) | The normative specification (RFC 2119 language) |
| [`RATIONALE.md`](RATIONALE.md) | Why the model exists — the non-normative argument |
| [`docs/related-work.md`](docs/related-work.md) | Positioning vs. Parasuraman–Sheridan–Wickens, SAE J3016, TM Forum Autonomous Networks, IBM autonomic computing |
| [`schema/lorm-policy.schema.json`](schema/lorm-policy.schema.json) | JSON Schema for the policy file, with [examples](schema/examples/) |
| [`skill/lorm/`](skill/lorm/) | A Claude Code Agent Skill implementing LORM as agent discipline |
| [`examples/`](examples/) | The model applied to [database operations](examples/database-operations.md), [coding agents](examples/coding-agent.md), [security ops](examples/cybersecurity.md) |

## Quick start

**1. Read the spec.** [`SPEC.md`](SPEC.md) — §2 (levels), §5 (invariants),
and §6 (trust lifecycle) are the core.

**2. Install the skill** into any Claude Code project:

```bash
cp -r skill/lorm /path/to/project/.claude/skills/lorm
```

The agent will then classify every state-changing action by LORM level,
perform diagnostics before proposing, present structured approval requests
at L4, and execute autonomously only what a valid policy grants.

**3. Write a policy** (optional — without one, everything state-changing is
L4). Start from
[`schema/examples/minimal.lorm-policy.yaml`](schema/examples/minimal.lorm-policy.yaml),
grow toward
[`full.lorm-policy.yaml`](schema/examples/full.lorm-policy.yaml). Validate:

```bash
python3 skill/lorm/scripts/validate_policy.py lorm-policy.yaml
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

- Specification 2.0.0 and the agent skill: **this repository, working**.
- Hard enforcement (PreToolUse hooks / policy engine consuming the same
  `lorm-policy.yaml`): planned; the schema is the forward contract.
- The skill provides *soft* enforcement — disciplined agent behavior, not a
  security boundary.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
