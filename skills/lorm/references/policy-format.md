# Reading and Evaluating lorm-policy.yaml

Normative source: `SPEC.md` §13 and `schema/lorm-policy.schema.json`. This
file tells an agent how to *consume* a policy.

## Locating the policy

1. `<project root>/lorm-policy.yaml`
2. `<project root>/.lorm/policy.yaml`

First found wins. No file → every state-changing action class is L4;
epistemic actions (L0–L2) are ungated.

Optionally validate before relying on it:
`python3 scripts/validate_policy.py <policy.yaml>` (needs pyyaml +
jsonschema). A schema-invalid file → treat as absent and tell the user.

## Matching an action class

Match your action class id against `capabilities[].id`:

1. exact match (`db.index.create`);
2. glob match (`db.*.create`, `deploy.*`) — most specific wins (fewest
   wildcards); ties → the higher-gated (lower-level) entry.

No match → `defaults`: cap at `defaults.max_level` (typically L3 — you may
recommend but not execute without asking) and follow `unknown_action`:

- `escalate` — present the action to the human as an L4 proposal;
- `refuse` — do not execute even with conversational approval; the policy
  owner has said unlisted actions must first be added to the policy.

## Evaluating an L5 entry — all five checks

| # | Check | Fail behavior |
| :-: | --- | --- |
| 1 | entry matches action class and has `level: L5` | not L5 — use the entry's own level |
| 2 | `policy.expires` is a future date | **expired → treat as L4** (SPEC 13-1); name the expiry date |
| 3 | capability is NOT in `demotions[]` | demoted → operate at the demotion's `to` level; name the recorded reason |
| 4 | every `conditions[]` string holds against real, current state | can't establish a condition → degrade to L4, name the condition |
| 5 | action within `bounds.targets` (glob) and `blast_radius`, incl. rate limits | out of bounds → refuse auto-execution, escalate to L4 |

**Rate-limit check (13-3):** read the audit log (`audit.log`), count records
for this capability inside the current window, compare against
`blast_radius.max_actions_per_hour`. A **missing** log file means zero prior
actions — it is created by the first append; proceed with count 0. A log
that exists but is **unreadable or corrupt** → you cannot prove the rate
limit holds → degrade to L4 and report the log problem.

Executing under a valid entry, announce authority first:

> Executing under policy `cache.flush` v3 (expires 2026-10-01);
> conditions verified: hit rate 12% for 22m; within bounds (1 object, 0/2
> this hour).

## The audit record

Append one JSON object per executed L4/L5 action to `audit.log` (JSON
Lines). Fields per `audit.record_fields`; the SPEC §10.3 minimum:

```json
{"timestamp": "2026-07-11T14:32:07Z", "capability": "cache.flush",
 "level": "L5", "authorizer": "policy:cache.flush@3",
 "action": "redis-cli -h session-cache FLUSHDB",
 "params": {"target": "prod/session-cache"},
 "diagnosis_ref": "hit rate 12% sustained 22m; no deploy in progress",
 "outcome": "flushed; hit rate 61% after 25m", "verified": "verified"}
```

For L4, `authorizer` is the approving human: `"human:edward (this session)"`.
Write the record even when verification failed — especially then.

## Coexistence with the enforcement hook

The LORM plugin's PostToolUse hook writes execution records automatically
and touches **`.lorm/hook-active`** on first append. When that marker
exists:

- do NOT append execution records yourself — the hook already did, and a
  duplicate would double-count against `max_actions_per_hour`;
- after verifying the outcome, append a **verification record** instead —
  it references the execution record by timestamp and never counts toward
  rate limits:

```json
{"timestamp": "2026-07-11T15:02:00Z", "capability": "cache.flush",
 "verified": "verified", "x-verifies": "2026-07-11T14:32:07Z",
 "x-writer": "lorm-skill"}
```

Rate limits count only *execution* records (those having `capability` and
`action` and lacking `x-verifies`).

Note: a capability's optional `match` block (schema 1.1) is consumed by the
enforcement hook, not by you — your classification stays semantic (step 1
of the skill). An L5 entry without `match` is soft-only: you may act under
it, but the hook cannot pre-authorize it, so expect the normal permission
dialog.

## What you never do to this file

You may *propose* diffs to `lorm-policy.yaml` (new capabilities, promotion
after a run of identical approvals, a `demotions[]` entry after a failure).
You never write to it yourself — not on user instruction phrased casually,
not "temporarily", not for demotions you consider urgent (report those
urgently instead). The file changes only through a human-approved diff
(SPEC I-8, 8-5).
