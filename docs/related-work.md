# Related Work and Positioning

*Non-normative. Expands SPEC.md Appendix A.*

Layered autonomy scales have been formalized repeatedly, in several domains,
over five decades. LORM stands on that lineage deliberately. This document
maps the predecessors and states precisely what LORM adds.

## Predecessor frameworks

### Sheridan–Verplank (1978) and Parasuraman–Sheridan–Wickens (2000)

The founding academic line. Sheridan and Verplank defined a 10-point scale of
automation, from "the computer offers no assistance" to "the computer decides
everything and acts autonomously, ignoring the human." Parasuraman, Sheridan
& Wickens (*A Model for Types and Levels of Human Interaction with
Automation*, IEEE SMC, 2000) refined it into a matrix: automation applies
independently to four information-processing functions — **information
acquisition, information analysis, decision selection, action
implementation** — each at its own level.

This is the closest academic ancestor of LORM's structure. The four PSW
functions map onto LORM's levels almost one-to-one:

| PSW function | LORM level(s) |
| --- | :-: |
| Information acquisition | L0–L1 |
| Information analysis | L2 |
| Decision selection | L3 |
| Action implementation | L4–L5 |

PSW's matrix insight — that automation level is set *per function*, not for
the whole system — reappears in LORM as per-capability level assignment
(SPEC §4). What PSW does not have is LORM's authorization axis: its levels
grade *how much* the machine does, not *who delegated the authority*.

### SAE J3016 (driving automation, L0–L5)

The namesake of the L0–L5 notation and of every "levels of autonomy" analogy
since. SAE grades the driving capability of the vehicle under specified
conditions (the Operational Design Domain). LORM borrows the notation and the
ODD idea (bounds, §8.3) but not the axis: an SAE level says what the car can
do; a LORM level says who authorized the action class.

### IBM Autonomic Computing (2001)

The direct ancestor for IT operations. IBM's initiative defined the MAPE-K
control loop (Monitor, Analyze, Plan, Execute over shared Knowledge) and a
five-step maturity ladder: Basic → Managed → Predictive → Adaptive →
Autonomic. MAPE-K's stages parallel L1→L2→L3→L4/L5; the maturity ladder
parallels the trust progression. LORM differs in granularity (per capability,
not per organization) and in making demotion — the downward direction — a
first-class, automatic mechanism. The autonomic-computing literature is
mostly silent on how autonomy is *withdrawn*.

### TM Forum Autonomous Networks (L0–L5)

The nearest industrial relative. TM Forum classifies telecom operations from
L0 (manual) to L5 (fully autonomous) and assesses each *operational scenario*
across five cognitive dimensions (Intent/Experience, Awareness, Analysis,
Decision, Execution), assigning each act to People (P) or System (S). Two of
LORM's commitments are shared with TM Forum: grading per scenario/capability
rather than per system, and locating the human explicitly in the loop
structure. The differences: TM Forum's ladder is a *target architecture*
for one industry, human intent persists to L4, and the framework describes
states, not transitions. LORM is domain-neutral, moves the watershed to the
authorization source, and specifies the promotion/demotion lifecycle.

### AI-agent autonomy taxonomies (2024–)

A fast-growing family: user-role scales (operator → collaborator → consultant
→ approver → observer), the Knight First Amendment Institute's *Levels of
Autonomy for AI Agents*, six-level hierarchies for data agents inspired by
SAE. These grade the *agent's* capability or the *human's* role in a
conversation. LORM is complementary rather than competing: it grades the
*action classes* the agent is allowed to touch, and supplies the artifact
(the policy) that makes any of those scales operationally enforceable.

### Self-driving databases

In database operations specifically — LORM's domain of origin — leveled
taxonomies have begun to appear. Postgres.AI's *Self-Driving Postgres*
(Samokhvalov, 2025) applies an SAE-J3016-style L0–L5 scale per operational area
(~25 areas: vacuum, bloat, indexes, config…), grading degree of automation
rather than authorization and specifying no delegation artifact and no trust
lifecycle. Oracle markets its Autonomous Database via the self-driving-car
analogy without a formal level model; the academic self-driving-DBMS line
(Pavlo et al.) focuses on capability, not authorization. The leveled-*notation*
niche is now occupied; the authorization-axis niche LORM defines is not.

## What LORM adds

1. **The authorization axis.** Predecessors grade capability or task-sharing;
   LORM grades the source of authority: none needed (L0–L2), human proposal
   review (L3), human per-action approval (L4), explicit versioned policy
   (L5). The question is never "can the system act?" but "who delegated the
   authority to act?"
2. **The policy as a first-class artifact.** Delegation is only legitimate
   when captured in a reviewable, versioned, *expiring*, tested document with
   separated author and approver (SPEC §8). No predecessor framework
   specifies the delegation artifact.
3. **The trust lifecycle.** Promotion is earned per capability on measured
   outcomes; demotion is automatic on defined triggers (SPEC §6). Predecessor
   frameworks are static ladders; LORM specifies the transitions, including
   the downward ones.
4. **Runtime degradation with stateful handback** (SPEC §7), importing the
   aviation lesson that the handover moment is the most dangerous part of
   high automation.
5. **Named human-factors failure modes** — approval fatigue at L4 and its
   countermeasures (SPEC §11) — rather than assuming the human control is
   real because it is present.

## Honest positioning statement

The ladder is not new, and LORM does not claim it is. TM Forum built nearly
the same ladder for networks; PSW built the matrix behind it in 2000; SAE
made the notation famous. LORM's claim is narrower and stronger: it moves the
grading axis from capability to delegated authority, attaches the lifecycle
that predecessor models leave out, and packages the result in a
machine-readable form that agents and enforcement layers can consume today.
