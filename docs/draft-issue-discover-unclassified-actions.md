# [Draft — not yet filed] Detect and propose tracking for recurring unclassified actions

*Unfiled GitHub issue draft, following `.github/ISSUE_TEMPLATE/feature_request.md`.
Written up 2026-07-18 during the same dogfooding session as
`draft-issue-mechanical-verification.md`. File to
https://github.com/Argyronix/lorm/issues when ready — until then this is a
local record only.*

**Affected layer:**
- [x] hooks/ (enforcement engine, classifiers) — new passive logging stream
- [x] skills/lorm (agent skill behavior) — new analyzer, parallel to
      `lorm_review.py`
- [ ] schema/lorm-policy.schema.json — not required for a first version
- [ ] SPEC.md — possibly an informative note on the discovery step that
      precedes §4-3 registration

**Problem**

Today, an action only becomes visible to LORM's tracking machinery
(`audit.jsonl`, `/lorm-review`) if it matches either an explicit
`capabilities[]` entry in `lorm-policy.yaml` or one of the **9 hard-coded**
classifiers in `hooks/classifiers.json` (`fs.delete`, `git.history.rewrite`,
`git.push`, `db.destructive`, `sys.config.change`, `pkg.install`,
`shell.indirect_exec`, `fs.write.outside_project`, `mcp.write_operation`).
That list is fixed by the plugin's authors and does not grow from observed
usage. Anything else falls through to Claude Code's native permission
dialog every time — by design ("Silence hands the call to Claude Code's
normal permission flow — that is the designed fallback, not a bug"), but
with the side effect that LORM assigns it no capability id and writes no
audit record. A user can approve the exact same routine, low-risk,
repetitive action dozens of times and LORM will never notice, never
propose registering it, and it will never surface in `/lorm-review` output
— not even as a hygiene finding, since hygiene findings are also computed
only over records that already carry a `capability` field.

This is a deeper blind spot than the one in `draft-issue-mechanical-
verification.md`: that issue is about actions LORM sees but never confirms
(`pending` forever); this one is about actions LORM never sees at all.

**Proposed change**

Add a new, generic, low-overhead passive log — e.g. `.lorm/observations.jsonl`,
kept separate from `audit.jsonl` (whose append-only guarantee and meaning
are specifically tied to named-capability execution/verification records)
— that records every gated tool call which matched neither a policy
capability nor a classifier. Capture only enough shape to cluster later:
tool name, a normalized/skeleton form of the command or path (not full
content — control log growth and avoid capturing payloads unnecessarily),
timestamp.

Then add a new analyzer (parallel to `lorm_review.py`, e.g.
`lorm_discover.py`, or an extension of the `/lorm:lorm-review` command)
that periodically clusters this log by `(tool, normalized-pattern)` and,
above a configurable repetition threshold within a window, proposes —
as a draft only, never auto-applied (SPEC I-8) — registering the pattern
as a new capability entry (entering at L3, per §4-3: "New capabilities
MUST enter the registry at the lowest level consistent with their nature")
with a suggested `match` block for the human to review, edit, and approve.

**Alternatives considered**

- Change `defaults.unknown_action` to force-log everything by default —
  a separate, narrower concern (just logging volume); doesn't itself solve
  discovery, which needs the clustering step regardless.
- Keep expanding `classifiers.json` with more hard-coded categories as
  maintainers notice new patterns — this is what happens today, informally,
  but doesn't scale: every project has its own routine patterns the
  maintainers can't anticipate in advance.
- Have the agent skill notice repetition conversationally, with no new
  logging — unreliable; same failure mode already identified in the
  mechanical-verification issue: depends on the calling agent's own memory/
  attention across sessions, not a structural guarantee.

**Compatibility**

Fully additive for a first version: new log file, new optional analyzer/
command; no change to `lorm-policy.yaml` schema or existing `audit.jsonl`
semantics required. A later version could add an opt-in threshold
configuration (e.g. under `defaults` in `lorm-policy.yaml`).

**Anything else**

Companion to `draft-issue-mechanical-verification.md` — together the two
would close most of the "quiet failure" surface identified while dogfooding
on the Argyronix_workspace project (2026-07-18): actions LORM tracks but
never confirms, and actions LORM never tracks in the first place.

Dependency: any capability this mechanism registers inherits the
verification gap described in `draft-issue-mechanical-verification.md` by
default — a newly-discovered capability can accumulate executions with zero
`verified` just like `fs.write.outside_project` did, unless that issue lands
first (or this one explicitly flags the gap at registration time).
