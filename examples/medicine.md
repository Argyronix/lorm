# LORM Applied: Clinical Operations

*Non-normative. Illustrative only — nothing here is clinical guidance, and
nothing here substitutes for the regulatory approval a medical device requires.*

Medicine is in this repository for a reason that has nothing to do with selling
software into hospitals. The model was assembled by looking at fields that had
already worked out how to let a machine participate in consequential decisions
without pretending the accountability moved with it. Clinical practice is the
oldest of those fields, and it is the one that most clearly shows the shape LORM
is trying to generalize: **a large lower estate, a deliberately small upper one,
and no embarrassment about the ratio.**

## The portfolio view

| Capability | Level | Authorization |
| --- | :-: | --- |
| `clin.records.observe` — patient history, medications, allergies, prior imaging | L0 | — |
| `clin.vitals.observe` — continuous monitoring, lab results, trends | L1 | — |
| `clin.diagnose.support` — differential with stated uncertainty and the findings it rests on | L2 | — |
| `clin.triage.recommend` — prioritization, escalation, "this deteriorating patient first" | L3 | clinician decides |
| `clin.treatment.recommend` — options with expected effect, contraindications, trade-offs | L3 | clinician decides |
| `clin.order.execute` — carry out an ordered intervention, within the ordered parameters | L4 | clinician, per order |
| `clin.insulin.deliver` — automated basal insulin adjustment inside clinician-set targets | L5 | policy: device-specific, target set by the prescriber, suspends on loss of sensor input |
| Diagnosis of record, treatment decisions, consent | L3 forever | the decision is a licensed human's; the system informs it |

## An honest ratio

SPEC §14 says most capabilities in most domains correctly never pass L3. Medicine
is where that is most obviously true, for two structural reasons rather than any
lack of model quality:

- **Outcomes verify slowly.** LORM will not promote a capability whose result
  cannot be checked (SPEC I-7). "Did this treatment work?" often resolves in
  weeks, by which time confounders have accumulated. Closed-loop glucose control
  is an exception precisely because the outcome is measured continuously, in
  minutes.
- **Errors are frequently irreversible.** Bounds can cap a dose; they cannot
  undo one.

So a truthful LORM portfolio in a hospital has a large L2–L3 estate, a modest L4
set, and an L5 set countable on one hand. A vendor claiming broad clinical L5 is
either describing something narrower than it sounds, or has not thought about
verification.

## What the one L5 capability actually looks like

Automated insulin delivery is the clearest real instance of the L5 pattern
outside software operations. Its structure maps onto the model almost line by
line:

- **Authority comes from a policy, not from a person in the moment.** The
  prescriber sets the glucose target and the constraints in advance; the
  algorithm then adjusts basal insulin without asking each time.
- **The bounds are narrow and explicit** — one hormone, one route, a declared
  target range, hard limits on rate.
- **Not everything is delegated.** Meal boluses stay with the person. These
  systems are called *hybrid* closed loop for exactly that reason: partial
  delegation is the design, not a limitation awaiting removal.
- **Loss of input forces degradation, not guessing.** When sensor data becomes
  unavailable, the loop suspends and hands control back — SPEC §7's stateful
  handback, in a device that predates the specification by years.
- **Delegation is revocable and reviewed.** The parameters are revisited at
  clinical appointments; nothing is granted permanently.

## What LORM does not do here

It does not make a device approvable. Regulatory clearance is a separate,
stricter gate, and a LORM level is not evidence for it. The model's contribution
in this domain is narrower: a vocabulary for stating which capability is at which
level and on whose authority — so that "AI-assisted" stops covering both a
suggestion on a screen and a pump changing a dose.
