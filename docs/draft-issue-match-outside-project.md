# [Draft — not yet filed] Policy match block cannot express "outside the project root"

*Unfiled GitHub issue draft, following `.github/ISSUE_TEMPLATE/feature_request.md`.
Written up 2026-07-19, noticed while implementing the 2.5.0/2.6.0 features.
Deliberately generic: the gap is a missing primitive of the policy language,
no usage data is needed to state it.*

***Status: implemented in plugin v2.7.0 (2026-07-21, schema 1.5 — see
CHANGELOG). Retained as the design record; file upstream only if
divergence is found.***

**Affected layer:**
- [x] hooks/ (enforcement engine — capability matching, pre and post)
- [x] schema/lorm-policy.schema.json (new `match` field)
- [ ] SPEC.md — no change; §13 already delegates match semantics to the
      consumer

**Problem**

The `match` block can express three kinds of coverage: `command_patterns`
(Bash segment text), `path_patterns` (the **project-relative** form of a
Write/Edit path), and `tool_patterns`/`input_patterns` (MCP). The built-in
classifier `fs.write.outside_project` matches via a fourth semantic — a
boolean `path_outside_project` flag — that has **no policy-side
equivalent**: a path resolving outside the project root has no
project-relative form (`norm_path` returns None), so no `path_patterns`
entry can ever cover it.

Consequently a policy capability registered for this action class is
permanently registry-only (soft), and the class is excluded from the whole
trust lifecycle:

1. **Pre:** the hook can never route the call through the policy entry —
   authorization stays with the classifier and `defaults`, regardless of
   what the entry declares.
2. **Post:** execution records attribute to the classifier hit, not the
   policy entry, so a schema-1.4 `verification.mechanical` block on the
   entry is never evaluated — the mechanical-verification feature is
   unavailable for precisely one of the nine built-in classes.
3. **L5:** delegation is structurally impossible — an entry without a
   usable `match` cannot produce `allow`, so no track record, however
   good, can be acted on (SPEC §6.2 promotion is a dead end here).

This is the only built-in class whose match semantics is a boolean rather
than a pattern; every other class can be overridden by a policy entry
whose `match` covers the same calls ("A policy overrides a built-in by
listing a capability whose match covers the command or tool" —
docs/hard-enforcement.md).

**Proposed change**

Schema **1.5**: an optional boolean `match.path_outside_project`
(mirroring the classifier flag), valid with `tools: [Write, Edit]`, added
to the `match` anyOf alongside the three pattern kinds.

Engine: `cap_matches_path` (and the post-side re-match) treat
"rel_path is None AND flag set" as a match. Flag-only matches carry
minimal specificity, so any patterned entry still wins the
most-specific tie-break. No bounds changes needed: `glob_path` already
matches absolute patterns against the absolute real path, so
`bounds.targets` with absolute globs give L5 entries real, hook-verified
canary scoping outside the project.

**Alternatives considered**

- Let `path_patterns` starting with `/` match the absolute path (the
  `glob_path` convention). Broader and also useful, but it silently
  changes the meaning of existing patterns that begin with `/` and blurs
  the documented "project-relative" contract; the boolean flag is
  narrower and reuses a semantic the classifier already defines.
- Post-only join by id (when a classifier hit's capability id equals a
  policy entry's id, use that entry's `verification` block). Fixes
  mechanical verification only; pre-routing and L5 stay closed, and it
  introduces an implicit name-coupling convention between classifiers
  and policies.
- Do nothing. Per-project this is livable (the class stays L4 with
  agent-/human-driven verification), but the asymmetry remains: the
  classifier can express a semantic the policy language cannot, which
  contradicts the override rule quoted above.

**Compatibility**

Fully additive: schema 1.5, new optional field; existing policies and all
prior schema versions behave unchanged. Entries without the flag remain
registry-only for this class, exactly as today.

**Anything else**

Interaction with the two implemented companions: mechanical verification
(2.5.0, `draft-issue-mechanical-verification.md`) cannot reach this class
until this lands (point 2 above); discovery (2.6.0,
`draft-issue-discover-unclassified-actions.md`) can never surface the gap
either, because outside-project writes always match the classifier and
therefore never reach the observations log.
