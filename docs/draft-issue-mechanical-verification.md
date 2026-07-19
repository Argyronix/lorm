# [Draft — not yet filed] Mechanical verification path for hook-checkable capabilities

*Written up 2026-07-18 after a week of dogfooding this plugin (v2.4.2) on the
Argyronix_workspace project, following `.github/ISSUE_TEMPLATE/feature_request.md`.*

***Status: implemented in plugin v2.5.0 (2026-07-19, schema 1.4 — see
CHANGELOG). Retained as the design record; file upstream only if
divergence is found.***

**Affected layer:**
- [x] hooks/ (enforcement engine, classifiers)
- [x] schema/lorm-policy.schema.json (new policy field)
- [ ] SPEC.md — possibly a clarifying note, not a normative change

**Problem**

Dogfooded on the Argyronix_workspace project (this exact plugin, v2.4.2) for
about a week (2026-07-11 → 2026-07-18). `fs.write.outside_project`
(Write/Edit outside project root) ran at L4, correctly gated, 69 executions.
Zero were ever verified. Root cause: `lorm_gate.py`'s PostToolUse hook always
writes `verified: pending` — turning that into `verified`/`failed` is
entirely delegated to the agent skill (SKILL.md §6), which never ran the
verify-and-append step for this capability, because its own trigger
heuristics target heavier operations (git push, deploy, DB migration), not
routine file writes. Net effect: a week of real, correctly-gated usage
produced zero progress toward promotion, and the human operator only
discovered this by explicitly running `/lorm-review` and having the hygiene
finding explained — there's no passive signal anywhere that verifications
are silently piling up as `pending`.

**Proposed change**

For capability classes whose success criterion is mechanically checkable
from data the hook already has (e.g., "target file exists post-write,
contains the intended string" vs. something needing judgment like "did this
VACUUM reduce bloat") — let the PostToolUse path evaluate it directly and
write `verified`/`failed` itself, instead of unconditionally deferring to an
agent step that may simply never run. Concretely: an optional
`verification.mechanical` block (file-exists / substring-match / exit-code
style checks only — no new expression language, consistent with the
existing "no conditions DSL" invariant) that the hook evaluates immediately
post-execution. Capabilities needing semantic judgment keep today's
agent-driven `x-verifies` path unchanged.

Independent smaller fix regardless of the above: surface pending-verification
counts passively (e.g. in the hook's `statusMessage`, or as part of the audit
write) so a user doesn't have to proactively run `/lorm-review` and interpret
a hygiene entry to notice that trust-lifecycle progress has stalled.

**Alternatives considered**

- Leave fully agent-driven, document the risk (what we did on the product
  side — a memory note telling the agent to remember). Doesn't scale: plugin
  correctness shouldn't depend on the calling agent's own persistent memory
  across sessions.
- Auto-verify everything mechanically — rejected, blurs the line between
  deterministic and judgment-requiring outcomes that SPEC deliberately
  separates.
- Have the skill run its full checklist after every gated Write/Edit —
  rejected, reintroduces the approval-fatigue/prompt-flood problem (§11) for
  what's often a cheap, deterministic check.

**Compatibility**

Additive — new optional field, old policies keep working via the existing
agent-driven path unchanged. No schema major bump needed.

**Anything else**

Related: `docs/trust-lifecycle.md`, SPEC §10.1, §I-7. Numbers behind this:
`fs.write.outside_project` — 69/69 `pending`, 0 `verified`, confirmed via
`lorm_review.py` output on 2026-07-18.

Dependency on `draft-issue-discover-unclassified-actions.md`: any capability
that discovery mechanism registers inherits this same verification gap by
default — worth landing this fix first, or at least flagging it in that
issue's rollout, so newly-discovered capabilities don't silently repeat the
`fs.write.outside_project` pattern (accumulating executions with zero
verified).
