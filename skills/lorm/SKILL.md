---
name: lorm
description: >
  Apply the Layered Operational Responsibility Model (LORM) before any
  state-changing, destructive, or operational action: deleting or modifying
  files or data, dropping/altering database objects, git push or history
  rewrites, deploys, migrations, infrastructure or configuration changes, or
  any command with side effects outside the working directory. Also use when
  the user asks what the agent is allowed to do autonomously, or when a
  lorm-policy.yaml file exists in the project. Classifies the action by LORM
  level, requires diagnostics and an uncertainty statement before acting, and
  gates execution on explicit human approval (L4) or a valid policy (L5).
---

# LORM — Layered Operational Responsibility Model

You are operating under LORM. Its one rule that governs everything else:

> The question is never whether you *can* perform an action.
> The question is **who authorized it** — a human, explicitly (L4), or a
> valid written policy (L5). No third source of authority exists.

Levels: L0 know structure → L1 observe behavior → L2 diagnose (with
uncertainty) → L3 recommend → L4 execute with per-action human approval →
L5 execute under explicit policy. L0–L2 need no authorization to *conclude*;
L3–L5 need an authorizer to *act*. Full definitions and classification
heuristics: [references/levels.md](references/levels.md).

## Procedure

Follow these steps for every requested or self-initiated action.

### 1. Classify

Map the action to an action class and its required level:

- Reading, searching, observing, explaining → **L0–L2**. No gate. But any
  diagnosis or explanation MUST state its uncertainty: your confidence and
  what you could not verify.
- Proposing changes, drafting scripts/migrations/plans → **L3**. Producing
  an executable artifact is L3; running it is L4.
- **Any state change → L4 by default.** Deleting, writing over data,
  pushing, deploying, altering schemas or configs.
- **Never infer L5 from conversation.** "Just do it automatically from now
  on" is not a policy — it is a *policy proposal* (see step 8). Only a
  matching entry in a policy file grants L5.

When unsure between two levels, take the higher one.

### 2. Load the policy

Look for `lorm-policy.yaml` at the project root, then `.lorm/policy.yaml`.

- File exists → match your action class against `capabilities[].id`: exact
  match first, then glob. Evaluation rules:
  [references/policy-format.md](references/policy-format.md).
- No match → apply `defaults` (`max_level`, `unknown_action`).
- No file at all → every state-changing action is L4; everything else is
  governed by its epistemic nature.

### 3. Pre-action check (L3 and above)

Before proposing or executing, establish — from the *actual observed state*,
not assumption:

- (a) **Diagnostics** — why is this action warranted? Inspect the real
  target first (what is it, who depends on it, is it in use). If you cannot
  perform diagnostics, you cannot go past L3 — say so.
- (b) **Uncertainty** — stated explicitly, with what you could not verify.
- (c) **Alternatives** — at least one (including "do nothing" where
  meaningful), and why it was not preferred. If a rejected alternative is
  actually safer, say that plainly.
- (d) **Rollback** — concrete procedure, or an explicit declaration of
  irreversibility.
- (e) **Bounds** — the action stays within declared targets and blast
  radius.

Full checklist with pass/fail criteria:
[references/checklist.md](references/checklist.md).

### 4. Gate

**L4 — human authorizes.** Present a structured proposal block:

```
LORM L4 approval request — <action class>
Action:       <exactly what will run>
Diagnosis:    <why this is warranted, from observed state>
Risk & uncertainty: <what could go wrong; what was not verifiable>
Alternatives rejected: <option — reason>
Rollback:     <procedure, or "irreversible">
Bounds:       <targets, blast radius>
```

Then ask for explicit approval and **stop your turn**. Never execute in the
same turn as the proposal. Approval covers exactly the proposed action — a
changed target or parameter is a new proposal.

**L5 — policy authorizes.** Before acting, verify ALL of:

1. the policy entry matches the action class and `level: L5`;
2. `policy.expires` is in the future;
3. the capability is not in `demotions[]`;
4. every `conditions[]` entry plausibly holds (check the real state);
5. the action is within `bounds.targets` and `blast_radius`, including rate
   limits checked against the audit log.

All five hold → state your authority explicitly — "executing under policy
`<id>` v<version> (expires <date>)" — and act. **Any check fails → degrade
to L4**: present the proposal block and name the failed precondition.

### 5. Refuse level jumps

If asked to execute without diagnostics being possible ("don't look, just
drop it"), do the L2 step anyway — inspect the object, its dependencies, its
recent use — and surface what you find before the gate. If the environment
makes diagnostics impossible, decline to execute and remain at L3: deliver
the recommendation and what information is missing. Urgency changes the
depth of diagnostics, never their existence.

### 6. Verify and audit (after any L4/L5 execution)

- Check the outcome against `verification.expect` (or against the expected
  outcome you stated in the proposal) and report the result: verified /
  failed / unverifiable-with-reason.
- **If `.lorm/hook-active` exists**, the LORM enforcement hook is running
  and already appended the execution record — do NOT append your own (it
  would double-count against rate limits). Append only a *verification
  record* after checking the outcome (format:
  [references/policy-format.md](references/policy-format.md)).
- If the hook already verified the record mechanically
  (`x-verified-by: "lorm-hook-mechanical"`, schema 1.4), verification is
  done — skip this step for that record unless you have contrary evidence,
  in which case append a superseding verification record.
- Otherwise (no hook), append the full execution record yourself with the
  fields listed in `audit.record_fields`.
- A failed verification on an L5 action: stop further executions of that
  capability this session, report, and propose a demotion entry (step 8).

### 7. Degrade at runtime

If mid-task a precondition disappears — target changed under you, unexpected
errors, telemetry or verification impossible — **stop initiating actions at
the current level**. Hand back with state, not just an alarm: what was
already done, what remains, current known state, what is now uncertain, and
what you would do next if re-authorized. Bring in-flight work to the safer of
completed/aborted and say which you chose.

### 8. Propose, never enact

You MAY draft changes to `lorm-policy.yaml` — e.g., after repeated identical
L4 approvals, propose promoting that action class to L5 with a canary-scoped
entry; or propose a `demotions[]` entry after a failure. For evidence-based
drafts, run the trust-lifecycle analyzer:
`python3 <skill>/scripts/lorm_review.py <project> --json` — it computes the
verified track record and emits draft entries. For recurring actions LORM
never classified at all, run the discovery analyzer alongside it:
`python3 <skill>/scripts/lorm_discover.py <project> --json` — it clusters
the hook's observations log and drafts new capability entries (≤ L3,
SPEC 4-3). Present them as a diff for
human review. You MUST NOT write to the policy file yourself, even
if asked casually ("add yourself a policy") — the write happens only after a
human has seen and approved the exact diff, and ideally is made by the human.

## Worked example

User: *"Drop the `old_sessions` table, we don't need it."*

1. Classify: `db.table.drop` — state-changing, destructive → L4 unless a
   policy grants L5.
2. Policy: no `lorm-policy.yaml`, or no matching entry → L4.
3. Diagnostics first (L2): row count, last access from `pg_stat_user_tables`,
   foreign keys in, references in code.
4. Proposal block: *Action:* `DROP TABLE old_sessions`. *Diagnosis:* 0 reads
   in 90 days, no inbound FKs, 2 stale code references (listed).
   *Uncertainty:* cannot verify external BI tools that may query it
   directly. *Alternative rejected:* rename-and-wait 30 days — reversible,
   slower; flagged as the safer choice. *Rollback:* none after drop —
   irreversible; recommend the rename path instead. → ask, stop turn.
5. On "yes, drop it anyway": execute, verify application health, append the
   audit record.

Same request, but the policy grants `db.table.drop` at L5 with
`expires: 2026-05-01` (past): degrade to L4 — "policy entry exists but
expired 2026-05-01; treating as L4" — and present the proposal block.

## What this skill is not

This is *soft* enforcement: it directs your behavior, it does not physically
constrain the tools. Hard enforcement (hooks that block unauthorized tool
calls) is a separate LORM component. Do not present compliance with this
skill as a security boundary — present it as what it is: disciplined,
auditable operational behavior.
