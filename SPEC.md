# LORM — Layered Operational Responsibility Model

**Specification, version 2.0.0**

LORM defines six progressive levels of operational responsibility (L0–L5) for
systems — AI-driven or conventional — that participate in operational
decision-making and action. Its central axis is not what a system *can* do,
but **who authorized it to act**.

---

## 0. Status, Versioning, Conformance — [Normative]

### 0.1 Requirement language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this
document are to be interpreted as described in RFC 2119.

Sections are marked **[Normative]** or **[Informative]**. Requirement
keywords carry RFC 2119 force only in [Normative] sections.

### 0.2 Versioning

This specification follows semantic versioning. The machine-readable policy
format (§13) carries its own version (`lorm_policy` field), incremented
independently.

### 0.3 Conformance

Two conformance targets exist:

1. **A LORM-conformant system** is one that: assigns a level to every
   capability it exposes (§4), satisfies the per-level requirements of §2 for
   each capability at its assigned level, upholds the invariants of §5, and —
   if it operates any capability at L4 or L5 — implements the lifecycle,
   degradation, verification, and audit requirements of §6–§10.

2. **A LORM-conformant policy** is a policy document that validates against
   the schema referenced in §13 and satisfies the lifecycle requirements
   of §8.

A system MAY be conformant while operating no capability above L3. Conformance
claims MUST name the highest level at which any capability operates.

---

## 1. Terminology — [Normative]

- **Capability** — a distinct class of operational action a system can
  perform, identified narrowly enough that one authorization decision
  meaningfully covers it (e.g. `db.vacuum.run`, `cache.flush`,
  `firewall.rule.add`). Synonym: **action class**.
- **Principal** — the human or organization accountable for operational
  outcomes in the domain where the system acts.
- **Authorizer** — whoever supplies the authority for a specific action
  execution: a human (L4 and below) or a policy (L5).
- **Policy** — a versioned, human-approved, machine-readable document that
  pre-authorizes a capability to execute within declared bounds (§8, §13).
- **Epistemic levels** — L0–L2: levels that grade what the system knows and
  understands.
- **Authority levels** — L3–L5: levels that grade what the system is
  permitted to do and who authorizes it.
- **Bounds** — the declared limits within which an L4/L5 capability may act:
  target scope, blast radius, rate limits, preconditions.
- **Blast radius** — the maximum extent of change a single action or action
  sequence may cause (objects touched, rate, magnitude).
- **Promotion** — raising a capability's assigned level after it meets the
  trust-lifecycle criteria (§6).
- **Demotion** — lowering a capability's assigned level, automatically on a
  demotion trigger (§6.3) or manually by the principal.
- **Degradation** — a *runtime* drop to lower-level behavior when a level's
  preconditions fail mid-operation (§7), as distinct from demotion, which is
  a durable change of assigned level.
- **Outcome verification** — the post-action comparison of observed results
  against the action's declared expected outcome (§10).

---

## 2. The Level Model — [Normative]

### 2.1 Overview

| Level | Name | Grades | The system may… | Question answered |
| :-: | --- | :-: | --- | --- |
| L0 | Structural Awareness | epistemic | know what exists: entities, topology, dependencies | "What exists?" |
| L1 | Behavioral Observation | epistemic | observe metrics, events, telemetry, trends | "What is happening?" |
| L2 | Diagnostics & Explanation | epistemic | explain causes, with stated uncertainty | "Why is it happening?" |
| L3 | Recommendation | authority | propose actions with tradeoffs and risks; never execute | "What should be done?" |
| L4 | Controlled Execution | authority | execute a specific action a human has authorized, within declared bounds | "May this approved action run safely?" |
| L5 | Policy-Driven Autonomy | authority | execute without per-action human approval, under an explicit, valid policy | "What may run under delegated authority?" |

Levels are cumulative: **no L(N) capability without the L(N−1) substrate.**
Higher levels never replace lower ones; they depend on them.

The seam between L2 and L3 is structural: **L0–L2 are epistemic levels**
(what the system knows), **L3–L5 are authority levels** (what the system is
permitted to do). Epistemic levels never require authorization to *conclude*;
authority levels always require an identified authorizer to *act*.

### 2.2 L0 — Structural Awareness

The system maintains a model of what exists in its operational domain:
entities, topology, dependencies, structural state.

- L0-1. A system claiming L0 for a domain MUST be able to enumerate the
  entities it operates on and their dependency relationships.
- L0-2. The structural model MUST have a defined refresh mechanism; its
  staleness MUST be knowable.

### 2.3 L1 — Behavioral Observation

The system observes behavior over the L0 structure: metrics, telemetry,
events, trends.

- L1-1. Observations MUST be attributable to entities in the L0 model.
- L1-2. The system MUST be able to state which signals it does *not* observe
  (known observability gaps), at minimum for the signals its L2+ conclusions
  depend on.
- L1-3. Loss of observation feeds MUST be detectable by the system itself.

### 2.4 L2 — Diagnostics & Explanation

The system explains why something is happening: causes, causal chains,
contributing context.

- L2-1. Every diagnosis MUST expose its uncertainty: a confidence estimate
  and the specific things the system could not verify.
- L2-2. Every diagnosis MUST be traceable to the L1 observations and L0
  structure that support it.
- L2-3. A diagnosis produced without supporting observations (assumption,
  extrapolation, prior belief) MUST be labeled as such.

### 2.5 L3 — Recommendation

The system proposes actions. Humans decide.

- L3-1. A recommendation MUST include: the proposed action, its expected
  outcome, its risks, and its rollback (or a statement of irreversibility).
- L3-2. A recommendation MUST include at least one considered alternative
  (including "do nothing" where meaningful) and why it was not preferred.
- L3-3. A recommendation MUST be grounded in an L2 diagnosis; recommending
  without diagnosis is a level jump (§5, I-1).
- L3-4. The system MUST NOT execute at L3. Producing an executable artifact
  (script, migration, plan) is L3; running it is L4.

### 2.6 L4 — Controlled Execution

The system executes a specific action that a human has explicitly authorized,
within declared bounds.

- L4-1. Human authorization MUST be explicit, per action or per named batch
  of actions, and MUST be recorded (who, what, when).
- L4-2. The proposal presented for authorization MUST contain the L3
  recommendation content (L3-1, L3-2) — the human must see what they are
  approving, not a bare confirmation prompt.
- L4-3. Execution MUST stay within the bounds stated in the proposal; any
  deviation discovered mid-execution triggers degradation (§7).
- L4-4. A rollback or mitigation path MUST exist, or irreversibility MUST
  have been declared in the proposal.
- L4-5. Every execution MUST produce an audit record (§10.3) and undergo
  outcome verification (§10.1).

### 2.7 L5 — Policy-Driven Autonomy

The system executes without per-action human approval. Authority comes from
an explicit, valid, human-approved policy.

- L5-1. Every L5 execution MUST be traceable to a specific policy entry:
  policy identifier, version, and the capability it covers.
- L5-2. The policy entry MUST be valid at execution time: not expired, not
  demoted, its preconditions met, the action within its bounds (§8, §13).
- L5-3. If any part of L5-2 cannot be positively established, the capability
  MUST degrade to L4 behavior for that action (§7).
- L5-4. L5 capabilities MUST have continuous observability of their own
  actions and outcomes; loss of that observability is a demotion trigger
  (§6.3).
- L5-5. Every execution MUST produce an audit record and undergo outcome
  verification, exactly as at L4.

L5 is not unlimited autonomy. It is **delegated operational authority**:
narrower, not broader, than what a human operator may do, because every
permitted action is enumerated in advance.

---

## 3. The Authorization Axis — [Normative]

LORM separates three properties that are commonly conflated:

- **capability** — what the system is technically able to do;
- **execution** — what the system actually does;
- **authority** — who authorized the doing.

> The level of a capability is determined by who authorizes its actions,
> not by what the system can do.

| Level | Authorization source |
| :-: | --- |
| L0–L2 | none required (epistemic conclusions) |
| L3 | none required to propose; a human decides what happens next |
| L4 | a human, explicitly, per action |
| L5 | a policy — written and approved by humans in advance |

Consequences:

- A system technically able to execute but lacking human authorization is at
  L3 for that capability, regardless of its sophistication.
- "The user told me to stop asking" is not a policy. Informal, conversational,
  or inferred delegation MUST NOT be treated as L5 authorization (§8).
- Removing the human from the moment of execution (L5) is only legitimate
  when the human's judgment has been captured in a reviewable, versioned,
  expiring artifact — the policy.

---

## 4. Per-Capability Level Assignment — [Normative]

- 4-1. Levels MUST be assigned per capability, never per system. "This
  system is L5" is not a meaningful LORM statement; "capability
  `cache.flush` operates at L5 under policy P v3" is.
- 4-2. A system is a **portfolio** of capabilities at different levels. A
  LORM-conformant system MUST maintain a capability registry: every exposed
  capability, its current assigned level, and — for L5 — the policy entry
  that grants it.
- 4-3. New capabilities MUST enter the registry at the lowest level
  consistent with their nature, and never above L3. Entry directly at L4
  requires a human authorization flow to exist; entry directly at L5 is
  prohibited (§6.2).
- 4-4. A capability's assigned level MUST be discoverable by the principal
  at any time, together with its promotion/demotion history.
- 4-5. Capability identifiers SHOULD use dotted action-class notation
  (`domain.object.verb`) and MUST be stable across policy versions.

*[Informative]* The portfolio view is what prevents both marketing inflation
("an L5 product") and blanket distrust ("no autonomy anywhere"). A mature
system typically runs most capabilities at L3–L4 and a small, well-measured
set at L5.

---

## 5. Invariants — [Normative]

The following invariants hold at all levels and take precedence over any
other provision of this specification.

- **I-1. No action without diagnostics.** No L4/L5 execution, and no L3
  recommendation, without a supporting L2 diagnosis grounded in L1
  observations of the actual current state.
- **I-2. No automation without explainability.** For every action, the
  system MUST be able to state why it acted, why alternatives were rejected,
  and why the action was considered safe — at the time of action, not
  reconstructed later.
- **I-3. No recommendation without uncertainty.** Every L2 conclusion and L3
  recommendation MUST carry an explicit uncertainty statement (L2-1).
- **I-4. No autonomy without bounded authority.** No L5 execution outside a
  valid policy entry with explicit bounds; no L4 execution outside the bounds
  of its human authorization.
- **I-5. Human responsibility remains explicit.** Every action MUST have an
  identifiable human accountable for it: the approver (L4) or the policy
  author and approver (L5). Responsibility never transfers to the system.
- **I-6. Every action is observable and auditable.** Every L4/L5 execution
  MUST produce an audit record (§10.3) before its effects are considered
  complete.
- **I-7. No execution without outcome verification.** Every L4/L5 action
  MUST have a declared expected outcome and MUST be verified against it
  (§10.1). Unverifiable actions are, by that fact, not eligible for L5.
- **I-8. Propose, never enact.** The system MAY propose changes to policies,
  its own bounds, or its own level assignments. It MUST NOT enact them. Every
  change to a policy or a level assignment requires human approval through
  the lifecycle of §6 and §8.

*[Informative]* Typical failure patterns are violations of these invariants:
blind automation is an L1→L5 jump (I-1); false confidence is recommendation
without uncertainty (I-3); unbounded autonomy is I-4; self-expanding agents
are I-8.

---

## 6. Trust Lifecycle: Promotion and Demotion — [Normative]

### 6.1 Principle

Trust is earned per capability, gradually, on evidence — and is lost
automatically, immediately, on defined triggers. Promotion is slow and
human-gated; demotion is fast and automatic.

### 6.2 Promotion

- 6-1. Promotion MUST proceed one level at a time. L3→L5 in one step is
  prohibited.
- 6-2. **L3→L4** requires: the capability has produced recommendations over a
  meaningful period; the principal has reviewed a sample and found the
  diagnoses sound (L3-3) and the risk statements accurate; a human
  authorization flow, bounds declaration, and rollback path exist.
- 6-3. **L4→L5** requires all of:
  - a track record at L4: a minimum number of executions (set by the
    principal, RECOMMENDED ≥ 10) with outcome verification passed and no
    unresolved incidents;
  - measured outcomes: verification results (§10) demonstrating the declared
    expected outcomes are reliably achieved;
  - a canary phase: the initial policy scope MUST be narrower than the
    intended final scope (fewer targets, tighter rate limits), widened only
    by subsequent policy versions;
  - a policy entry satisfying §8, approved by a human other than its author.
- 6-4. Promotion decisions MUST be made by the principal (or their delegate),
  never by the system (I-8). The system SHOULD surface promotion candidacy —
  e.g. "this capability has 40 approved identical executions; here is a draft
  policy" (§11).

### 6.3 Demotion

- 6-5. The following are mandatory automatic demotion triggers. On any of
  them, the affected capability MUST immediately drop one level (L5→L4,
  L4→L3) without waiting for human review:
  - an incident attributed to the capability's action;
  - invocation of the capability's rollback;
  - outcome verification failure (§10.1) not explained and accepted by the
    principal;
  - loss of the telemetry needed for the capability's diagnostics or
    verification (L5-4);
  - uncertainty above the threshold declared in the policy or proposal;
  - policy expiry or revocation (L5 only — the capability reverts to L4).
- 6-6. Demotions MUST be recorded (what, when, trigger, evidence) and
  reported to the principal.
- 6-7. Re-promotion after demotion MUST follow the full promotion path of
  §6.2 — the prior track record does not carry over past the incident.
- 6-8. The principal MAY demote any capability at any time without cause.

---

## 7. Runtime Graceful Degradation — [Normative]

Degradation governs what happens *during* an operation when the conditions
that justified the current level stop holding.

- 7-1. If a level's preconditions fail mid-operation — telemetry loss,
  unexpected state, bounds ambiguity, verification impossibility, errors of
  an unanticipated kind — the capability MUST stop initiating new actions at
  that level and degrade at least one level for the remainder of the
  operation.
- 7-2. Degraded handback MUST carry state, not just an alarm. The handback
  report MUST include: what was already done, what remains undone, current
  known state, what is now uncertain, and what the system would do next if
  re-authorized. A bare "manual intervention required" is non-conformant.
- 7-3. In-flight actions that can be safely completed or safely aborted
  SHOULD be brought to the safer of those two states before handback;
  which one was chosen MUST be reported.
- 7-4. Degradation is temporary and scoped to the operation. Whether it also
  constitutes a demotion trigger is determined by §6.3, evaluated separately.

*[Informative]* This is the automation-handback problem known from aviation:
the most dangerous moment of high automation is the transfer of control back
to the human, because it tends to happen precisely when the situation is
already abnormal — and the human has been out of the loop. LORM therefore
puts the burden of context transfer on the system.

---

## 8. L5 Policy Lifecycle — [Normative]

A policy is the artifact that carries delegated authority. Its lifecycle is
where human responsibility for L5 lives (I-5).

- 8-1. Every L5 policy entry MUST carry: a version; an author; an approver
  **different from the author**; an approval date; an expiry date; and
  evidence of testing (what was tested, when, with what outcome) prior to
  activation.
- 8-2. Expiry is mandatory. Policies without expiry dates are non-conformant.
  On expiry the capability reverts to L4 automatically (§6.5). Renewal is a
  new approval, and SHOULD include review of the capability's verification
  record since the last approval.
- 8-3. Policies MUST declare, per capability: bounds (targets, blast radius,
  rate limits), preconditions, the expected outcome for verification, the
  escalation path on failure, and rollback (or declared irreversibility —
  in which case L5 eligibility SHOULD be reconsidered, see I-7).
- 8-4. Policies MUST be versioned; scope widening (more targets, higher
  limits) is always a new version with new approval.
- 8-5. Policy changes follow I-8: the system MAY draft and propose them
  (as a reviewable diff), and MUST NOT activate them. Activation is a human
  act.
- 8-6. Revocation MUST be possible at any time, MUST take effect before the
  capability's next action, and MUST NOT require the system's cooperation
  (a human-reachable kill switch outside the system's own control path
  SHOULD exist).

---

## 9. Composition and Arbitration — [Normative]

Capabilities do not act in a vacuum. When several L4/L5 capabilities can act
on the same objects, their interaction MUST be governed.

- 9-1. Two autonomous (L5) capabilities MUST NOT concurrently modify the
  same object unless an explicit arbitration rule covers that pair (mutual
  exclusion, defined precedence, or a coordinating scheduler).
- 9-2. Every L4/L5 capability MUST declare its blast radius (§13): the
  maximum objects per action, actions per time window, and scope of targets.
  Declared blast radii are the units arbitration reasons over.
- 9-3. When two capabilities' preconditions fire on the same object, the
  one with higher declared precedence acts; the other MUST record that it
  yielded, and escalate if its condition persists.
- 9-4. Cumulative effects MUST be bounded: rate limits apply across all
  capabilities acting on an object class, not only within one capability,
  where the policy declares a shared budget.

*[Informative]* The classic failure here is two well-behaved control loops
producing oscillation: a tuner enlarging a resource while a cost optimizer
shrinks it. Each is safe alone; the pair is an incident. Arbitration
declarations make the pair a designed object rather than an accident.

---

## 10. Outcome Verification and Audit — [Normative]

### 10.1 Outcome verification

- 10-1. Every L4/L5 action MUST have, before execution, a declared expected
  outcome and a verification window (how long after execution the outcome is
  checked).
- 10-2. After execution, the system MUST compare observed state against the
  expected outcome within the window and record the result: `verified`,
  `failed`, or `unverifiable` (with reason).
- 10-3. `failed` triggers §6.3 evaluation. Repeated `unverifiable` results
  for a capability MUST be surfaced to the principal and SHOULD block L5
  eligibility (I-7).
- 10-4. Verification results accumulate into the capability's trust record —
  the evidence base for promotion (§6.2) and policy renewal (§8.2).

### 10.2 Audit — scope

Audit makes I-6 concrete: every execution leaves a record sufficient to
reconstruct *what* happened, *why*, and *under whose authority*.

### 10.3 Audit record — minimum fields

Every L4/L5 execution's audit record MUST contain at least:

| Field | Content |
| --- | --- |
| `timestamp` | when the action ran |
| `capability` | the action-class identifier |
| `level` | level at which it ran (after any degradation) |
| `authorizer` | the approving human (L4) or policy id + version (L5) |
| `action` | what was actually executed |
| `params` | concrete parameters/targets |
| `diagnosis_ref` | reference to the supporting L2 diagnosis |
| `outcome` | observed result |
| `verified` | verification status per §10.1 |

Audit records MUST be append-only from the system's perspective and MUST be
retained per the principal's retention policy.

---

## 11. Human Factors at L4 — [Normative]

Approval fatigue is a named failure mode of this model: a human who approves
hundreds of near-identical L4 requests stops being a control and becomes a
rubber stamp — the form of L4 without its substance.

- 11-1. Systems operating at L4 SHOULD detect repeated approval of
  materially identical requests and respond by proposing a policy (the
  legitimate L4→L5 bridge, per §6.4 and I-8) — converting reflexive
  approvals into one deliberate, reviewable delegation decision.
- 11-2. Approval requests SHOULD be rate-limited or batched; a flood of
  individual prompts is itself a design defect.
- 11-3. Approval prompts MUST make the riskiest element of the request the
  most prominent (L4-2); uniform, template-identical prompts for actions of
  very different risk are non-conformant with the intent of L4.
- 11-4. Principals SHOULD periodically sample approved L4 actions for deep
  review, treating high approval rates not as evidence of safety but as a
  signal that either the capability is ready for a policy or the approvals
  have degraded into ritual.

*[Informative]* Field data from agentic-tooling vendors shows the large
majority of permission prompts in high-volume settings are approved
reflexively. The honest responses are exactly two: make the approval real
(fewer, richer prompts) or make the delegation real (an explicit policy).
L4-as-ritual is the dishonest third state this section exists to prevent.

---

## 12. Validation Checklist — [Normative]

A capability MUST pass this checklist before assignment to L3 or above, and
on every promotion. The checklist is evaluated per capability, recorded, and
kept with the capability registry (§4).

1. What level is requested for this capability, and what is its exact
   action-class scope?
2. What L0 structural knowledge does it require, and how fresh must that be?
3. What L1 observations does it depend on, and how is their loss detected?
4. What L2 diagnosis supports action, and how is it traced to observations?
5. How is uncertainty estimated, expressed, and thresholded?
6. What confidence threshold gates action, and what happens below it?
7. What exact actions are possible, and what is excluded?
8. What are the expected outcomes and risks, and how are outcomes verified
   (§10.1)?
9. Who authorizes: human per action (L4) or which policy (L5)?
10. What happens when the authorizer disagrees or withholds approval —
    is there a coercion-free stop?
11. What bounds, rate limits, and rollback mechanisms exist (§8.3, §9.2)?
12. Is every execution observable and auditable per §10.3?
13. Can the system explain, at action time: why it acted, why alternatives
    were rejected, why the action was considered safe (I-2)?
14. Does the capability remain within bounded authority under composition
    with every other L4/L5 capability that shares its targets (§9)?

---

## 13. Machine-Readable Policy Format — [Normative]

The normative schema for LORM policies is
[`schema/lorm-policy.schema.json`](schema/lorm-policy.schema.json)
(JSON Schema, draft 2020-12), applied to a YAML or JSON document
conventionally named `lorm-policy.yaml`.

Summary of the format (the schema is authoritative):

- `lorm_policy` — policy format version.
- `metadata` — project, owner, last-updated date.
- `defaults` — behavior for capabilities not listed: `max_level` (RECOMMENDED
  `L3`), `unknown_action` (`escalate` or `refuse`), `uncertainty_threshold`.
- `capabilities[]` — per capability: `id` (dotted action class; consumers
  match exact first, then glob), `level`, `bounds` (targets, blast radius,
  rate limits), `rollback`, `verification.expect`; and for L5 additionally
  the `policy` block (version, author, approver ≠ author, approval date,
  **mandatory `expires`**, testing evidence), `conditions[]`, and
  `escalation`.
- `audit` — audit log location and required record fields (§10.3).
- `demotions[]` — active demotions; a demotion entry **overrides** the listed
  capability level for consumers (§6.5).

Consumer rules:

- 13-1. A consumer (agent, skill, or enforcement plugin) MUST treat an
  expired, demoted, or schema-invalid L5 entry as L4.
- 13-2. A consumer MUST treat the absence of a policy document as: all
  state-changing capabilities at L4, all others per their epistemic nature.
- 13-3. Consumers MUST evaluate rate limits against the audit log named in
  `audit.log` before acting under an L5 entry.
- 13-4. Unknown fields prefixed `x-` MUST be ignored, not rejected
  (extensibility); `conditions` entries are human/agent-interpretable strings
  in this version — a structured machine-evaluable form is reserved for a
  future schema version.

---

## 14. Applicability and Limits — [Informative]

LORM assumes an environment with observable telemetry, measurable outcomes,
bounded action spaces, and feedback loops — operational systems. It is a
poor fit for domains with weak causality or unmeasurable outcomes: strategy,
politics, speculative investment.

Not every capability should reach L5. For many, L3 or L4 is the correct
permanent endpoint — irreversible actions with unverifiable outcomes are
structurally ineligible (I-7). A LORM-conformant system with zero L5
capabilities is not an immature system; it may simply be an honest one.

---

## Appendix A. Related Work and Positioning — [Informative]

Layered autonomy scales are an established idea. LORM's contribution is the
axis it grades on, and the lifecycle it attaches.

| Framework | Domain | What its levels grade |
| --- | --- | --- |
| Sheridan–Verplank (1978); Parasuraman–Sheridan–Wickens (2000) | human–automation interaction | degree of automation across four functions (acquisition, analysis, decision, action) |
| SAE J3016 (L0–L5) | driving automation | driving capability under conditions |
| IBM Autonomic Computing (2001), MAPE-K, 5 maturity levels | IT operations | organizational/technological maturity of self-management |
| TM Forum Autonomous Networks (L0–L5) | telecom | per-scenario allocation of cognitive acts to People vs System |
| AI-agent autonomy taxonomies (2024–) | LLM agents | agent capability and human role |

LORM's differences:

1. **The axis is authorization, not capability.** PSW, SAE, and agent
   taxonomies grade what the machine does; LORM grades who delegated the
   authority. TM Forum's People/System allocation is the nearest relative;
   LORM generalizes it across domains and makes the delegation artifact (the
   policy) a first-class, versioned, expiring object.
2. **Levels attach to capabilities, not systems** (§4) — closer to TM Forum's
   per-scenario grading than to SAE's whole-vehicle levels.
3. **A trust lifecycle is part of the model** (§6): earned promotion,
   automatic demotion. The predecessor frameworks describe states; LORM also
   specifies the transitions.
4. **PSW's four functions map onto the epistemic/authority seam**: their
   acquisition/analysis correspond to L0–L2, decision to L3, action to
   L4–L5 — see `docs/related-work.md` for the full mapping.

## Appendix B. Changes from v1 and Traceability — [Informative]

### B.1 Changes from v1

| v1 | v2 |
| --- | --- |
| §1 Why This Model Exists | moved to `RATIONALE.md` |
| §2 What Is the Model, §4 Layer definitions | §2, condensed; per-level MUSTs added |
| §3 Core Principles | §5 Invariants I-1…I-6, tightened; I-7, I-8 new |
| §5 Human vs System Authority | §3 |
| §6 Why Most AI Systems Fail | one informative note under §5; prose to `RATIONALE.md` |
| §7 Why Layered Responsibility Works | `RATIONALE.md` |
| §8 Special Nature of L5 | absorbed into §2.7 and §8 (policy lifecycle) |
| §9 Cross-Domain Examples | `examples/` |
| §10 Checklist | §12, reworded operationally |
| §11 Boundaries and Limitations | §14 |
| §12 Final Observation | `RATIONALE.md` |
| — | §0, §1, §4, §6, §7, §9, §10, §11, §13, App. A/B: new |

Terminology: v2 standardizes on **level** (v1 mixed "layer"/"level") and
retains v1's prohibition on the retired IM/DM vocabulary.

### B.2 Invariant traceability

| Invariant | Checklist item(s) (§12) | Policy schema field(s) (§13) |
| :-: | :-: | --- |
| I-1 | 2, 3, 4 | `conditions` (preconditions grounded in observation) |
| I-2 | 13 | `diagnosis_ref` audit field |
| I-3 | 5, 6 | `defaults.uncertainty_threshold` |
| I-4 | 1, 7, 11, 14 | `capabilities[].bounds`, `level` |
| I-5 | 9, 10 | `policy.author`, `policy.approved_by`, `authorizer` audit field |
| I-6 | 12 | `audit.log`, `audit.record_fields` |
| I-7 | 8 | `verification.expect`, `verified` audit field |
| I-8 | 10 | `demotions[]` (human-maintained), policy versioning |
