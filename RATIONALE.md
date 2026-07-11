# LORM Rationale

*This document is **non-normative**. It preserves the motivation and argument
of the model. For requirements, see [SPEC.md](SPEC.md).*

## Why this model exists

Modern AI systems increasingly participate in operational decision-making:
infrastructure management, cybersecurity, medicine, industrial automation,
finance, logistics, software operations.

Most of them share one fundamental defect: they try to jump directly from
observation to autonomous action — from data collection to automation, from
prediction to execution. When that happens, explainability is lost,
auditability disappears, autonomy becomes unbounded, humans lose their mental
model of the system, and responsibility becomes unclear.

The underlying error is treating autonomy as binary: either fully manual or
fully autonomous. LORM's premise is different:

> Autonomy is not binary. Operational responsibility must evolve
> progressively and transparently.

The model's purpose is not automation for its own sake. It is controlled
operational intelligence: explainable decision-making, bounded autonomy, and
explicit delegation of responsibility.

## Why most systems fail

The typical failure patterns are level jumps:

| Unsafe jump | Result |
| --- | --- |
| observation → autonomous action (L1→L5) | blind automation |
| diagnosis → execution without authorization | unsafe action generation |
| prediction without diagnostics | no causal understanding |
| automation without policy boundaries | unbounded autonomy |
| recommendations without uncertainty | false confidence |

The consequences are always the same: loss of trust, non-auditable decisions,
operator confusion, operational instability. The model prevents them by
enforcing progressive delegation — each invariant in SPEC §5 is the negation
of one of these jumps.

## Why layered responsibility works

**Explainability by design.** Higher levels cannot exist without lower-level
visibility and diagnostics, so the system can always explain its
observations, reasoning, decisions, and actions — the explanation path is
the same path the decision took.

**Bounded autonomy.** Autonomy is constrained by policy, authority,
observability, and declared operational limits, which prevents uncontrolled
behavior without prohibiting autonomy itself.

**A preserved human mental model.** Humans remain able to understand system
state, reasoning, intended actions, and risks. The system does not become an
opaque black box, because opacity at any level disqualifies the levels above
it.

**Progressive trust.** Trust is not assumed; it accumulates through
observation, explanation, recommendation, supervised execution, and only then
bounded autonomy — and it drains instantly on failure (SPEC §6). Trust that
cannot be lost is not trust; it is negligence.

**Operational auditability.** Every step is observable, explainable,
reviewable, and attributable — the property regulated and safety-critical
environments require, and every other environment eventually discovers it
needs.

## The special nature of L5

L5 is not "more automation" or "smarter AI." It is **delegated operational
authority**. At every level below, a human is present at the moment of
decision; at L5, the human's judgment arrives earlier, captured in a policy.
That is why the policy — versioned, approved, expiring, testable — is the
central artifact of the model, and why a system that cannot point to the
policy authorizing an action has no business executing it.

## Final observation

LORM is not primarily a model of automation. It is a model of operational
responsibility, explainable intelligence, bounded autonomy, and progressive
delegation of authority.

Its central idea is simple:

> A system must first observe, then understand, then explain, then recommend,
> then safely execute — and only then operate autonomously within explicitly
> delegated boundaries.
