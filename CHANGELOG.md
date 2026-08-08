# Changelog

The LORM specification follows semantic versioning. The policy schema version
(`lorm_policy` field) is versioned independently of the specification.

## 2.7.1 — 2026-08-08

Two defects found by installing the plugin from the marketplace into an empty
project and taking one action — the thing CI structurally cannot do.

### Fixed
- `.lorm/hook-active` is now created by the **pre** hook on the first gated
  call, not by the post hook on its first audit append. The skill checks for
  that marker in the same turn as the action it just took, and in a fresh
  project the post-side append had not landed yet: the skill concluded no hook
  was running and appended its own execution record beside the hook's. Two
  records for one action, and `max_actions_per_hour` spent twice as fast — a
  capability limited to 2 per hour lost half its quota to a single action. The
  race fired exactly once per project, on the first authorized action, which is
  also the first thing a new user does. Marker writing is best-effort and
  wrapped: bookkeeping never affects a decision.
- 6 new checks (119 total), including that the marker exists after the pre call
  and before any audit record, that it appears even when the decision is
  silence, and that a project with no policy file still gets no marker at all.

### Changed
- The skill now takes `timestamp` from `date -u +%Y-%m-%dT%H:%M:%SZ` and both
  skill documents say plainly that the field is UTC. Nothing had said so, and
  the model stamped local time with a `Z` suffix — three hours off, in a field
  the rate-limit window is computed from. The hook was always correct here; the
  skill's manually written records were not.

### Notes
- No schema change; `SPEC.md` unchanged. Policies and audit logs written by
  earlier versions stay valid, including logs that already contain a duplicate
  pair — `/lorm:lorm-review` counts them as written, so a capability that
  looks close to its rate limit may simply be carrying one.

## 2.7.0 — 2026-07-21

Outside-project writes can now be claimed by policy. Closes the asymmetry
where the built-in `fs.write.outside_project` classifier could express a
match semantic (a path outside the project root) that the policy language
could not, leaving that one class permanently outside the trust lifecycle.

### Added
- Schema 1.5: optional boolean `match.path_outside_project` (with
  `tools: [Write, Edit]`), a fourth `match` variant alongside
  `command_patterns` / `path_patterns` / `tool_patterns`. Mirrors the
  built-in classifier semantic that no `path_patterns` entry can cover
  (an outside path has no project-relative form).
- Enforcement engine: `cap_matches_path` treats "path outside project AND
  flag set" as a match for Write/Edit, so a policy entry now (1) routes
  pre-authorization through the entry instead of the classifier, (2) gets
  post-side attribution to the entry — enabling schema-1.4
  `verification.mechanical` for this class — and (3) becomes eligible for
  L5 delegation. A flag-only match has minimal specificity, so patterned
  entries still win the most-specific tie-break.
- L5 scoping for outside writes reuses existing `bounds.targets` with
  absolute globs (`glob_path` already matches absolute patterns); no
  bounds changes. Project-relative targets never match an outside path and
  safely degrade to L4.
- 9 new tests (113 total).

### Notes
- Fully additive: policies without the flag and all prior schema versions
  behave exactly as before. `SPEC.md` unchanged (§13 delegates match
  semantics to the consumer). The `fs.write.outside_project` classifier is
  unchanged and remains the fallback when no policy entry claims the class.

## 2.6.0 — 2026-07-19

Discovery — actions LORM never saw now leave a trace and become draft
policy. Design record: `docs/draft-issue-discover-unclassified-actions.md`
(companion to 2.5.0's mechanical verification; shipped second so
newly-discovered capabilities can point at the verification fix instead
of inheriting the gap).

### Added
- Passive observations log `.lorm/observations.jsonl`: gated calls
  matching neither a policy capability nor a built-in classifier are
  recorded as (timestamp, tool, skeleton, session) — normalized shape
  only, never values or payloads (`git commit -m "fix"` →
  `git commit -m «ARG»`; a Write of `src/x.py` → `src/*.py`; MCP → tool
  name + sorted input field names). Size-capped at 512 KiB with
  oldest-half truncation; carries no append-only guarantee (that remains
  audit.jsonl's). The skill's own log/policy traffic is filtered out.
- `skills/lorm/scripts/lorm_discover.py`: clusters observations by
  (tool, skeleton) within `--window` (default 30d) and, at or above
  `--min-count` (default 5), emits draft capability entries — entering at
  L3 per SPEC 4-3, skeleton converted to a `match` block, with explicit
  notes on L3-deny semantics and the verification gap (add
  `verification.expect` / schema-1.4 `mechanical`). Drafts only, never
  applied (I-8).
- `/lorm:lorm-review` now runs both analyzers and reports a discovery
  section alongside promotions/demotions/expiry/hygiene.
- SPEC.md 2.0.2: informative note after §4-3 (registration presupposes
  noticing; shape-only passive recording; I-8).
- 18 new tests (104 total).

## 2.5.0 — 2026-07-19

Mechanical verification — deterministically checkable outcomes no longer
depend on the agent remembering to verify. Design record:
`docs/draft-issue-mechanical-verification.md` (dogfooding evidence:
`fs.write.outside_project`, 69/69 executions stuck `pending`).

### Added
- Policy schema **1.4**: optional `verification.mechanical.checks[]` —
  `file_exists` / `file_contains` / `output_contains` / `exit_code`,
  evaluated by the PostToolUse hook immediately after execution. All pass
  ⇒ the audit record is written `verified` (with
  `x-verified-by: "lorm-hook-mechanical"`); any fail ⇒ `failed`, feeding
  the existing demotion path; a check that cannot be evaluated leaves the
  record `pending` (agent path unchanged). Fixed vocabulary by design —
  not an expression language. `$TOOL_FILE` token references the
  Write/Edit file_path.
- Exit-code recovery from dict-shaped `tool_response` payloads (multiple
  Claude Code field spellings probed; `interrupted`/`is_error` count as
  failed; unknown ⇒ pending). Bash `outcome` and `output_contains` now
  see stderr as well as stdout.
- Passive pending-verification surfacing: the post hook emits a
  `systemMessage` on mechanical verification failure, and when a
  capability's unsuperseded pending count reaches exactly 10/25/50/100
  with zero verified — stalled trust-lifecycle progress no longer waits
  for someone to run `/lorm-review`.
- `validate_policy.py` warnings: `exit_code` on a non-Bash-matched
  capability; `mechanical` combined with a non-trivial
  `verification.window`.
- SPEC.md 2.0.1: informative note after §10.1 (the verifier need not be
  an agent when the outcome is deterministically checkable).
- 13 new tests (86 total).

## 2.4.2 — 2026-07-11

### Fixed
- **Narrow L5 exceptions inside broad L4 catch-alls were unreachable.**
  With `fs.delete` at L4 (`"rm *"`) and a canary L5 (`"rm .tmp-*"`), both
  matched and most-restrictive-wins always chose L4 — found while
  dogfooding a real policy. Now, when several capabilities match the same
  segment/call, the most specific pattern (most literal characters) wins;
  exact ties still combine most-restrictively. Applies to Bash, Write/Edit,
  and MCP matching, and to post-hoc audit attribution.
- Test fixture bug: appended capabilities landed after the audit block,
  so one multi-capability test passed via a YAML parse error rather than
  the intended path.

## 2.4.1 — 2026-07-11

### Fixed
- Plugin failed to load when installed from the marketplace: `hooks/hooks.json`
  is auto-discovered by Claude Code, and the explicit `"hooks"` manifest field
  made it load twice ("Duplicate hooks file detected"). The manifest field is
  removed; found by dogfooding the marketplace install.

## 2.4.0 — 2026-07-11

Executable conditions — the last soft check on the L5 allow path can now
be deterministic.

### Added
- Policy schema **1.3**: `conditions[]` entries may be objects
  `{text, check, timeout}`. The enforcement hook runs `check` from the
  project root (env: LORM_CAPABILITY, LORM_TOOL_NAME, LORM_ACTION,
  CLAUDE_PROJECT_DIR); exit 0 = holds; non-zero/timeout/budget-exhausted
  → degrade to L4 naming the condition. Per-check timeout ≤ 8 s, overall
  budget 8 s. Plain strings remain agent-verified and are noted as such
  in the allow reason.
- Threat-model note: checks are part of the human-approved, P1-protected
  policy file and run with the same privileges the gated action would.
- 6 new tests (71 total).

## 2.3.0 — 2026-07-11

Trust-lifecycle tooling — the SPEC §6 promotion/demotion lifecycle made
operational.

### Added
- `skills/lorm/scripts/lorm_review.py`: deterministic audit-log analyzer.
  Joins execution and verification records; reports promotion candidates
  (with draft L5 policy entries: track record, canary expiry, derived rate
  limit, DRAFT placeholders for author/approver), demotion proposals on
  failed verifications, policy-expiry warnings, and hygiene findings
  (verification coverage too low to promote — I-7 applied to tooling).
- `/lorm:lorm-review` plugin command: runs the analyzer and presents
  drafts as human-reviewable diffs; I-8 forbids self-applying them.
- `docs/trust-lifecycle.md`.
- 9 new tests (65 total).

## 2.2.0 — 2026-07-11

MCP tool coverage.

### Added
- The enforcement hooks now gate MCP tools (`mcp__*`) alongside
  Bash/Write/Edit; action-class mapping `mcp__<server>__<tool>` →
  `mcp.<server>.<tool>`.
- Policy schema **1.2**: `match.tool_patterns` (fnmatch vs the MCP tool
  name) and `match.input_patterns` (per-field fnmatch vs `tool_input`,
  AND semantics, non-strings matched via JSON serialization). Additive;
  1.0/1.1 policies remain valid.
- Built-in classifier `mcp.write_operation`: unlisted mutating-verb MCP
  tools route through `defaults.unknown_action`; read-only verbs pass
  through.
- 10 new test cases (56 total).

### Known limitations
- P1/P2 self-protection cannot see policy-file writes made through MCP
  filesystem servers.
- `bounds.targets` are not hook-verifiable for MCP capabilities — the
  target scope MUST be encoded in `input_patterns`.

## 2.1.0 — 2026-07-11

Hard enforcement: the repository is now a Claude Code plugin.

### Added
- `.claude-plugin/plugin.json` + `marketplace.json` — install the repo as a
  plugin (`claude --plugin-dir` or via marketplace); one install ships both
  the skill and the hooks.
- `hooks/scripts/lorm_gate.py` — PreToolUse authorization gate and
  PostToolUse audit writer for Bash/Write/Edit. Decision table, matching
  semantics, and threat model: `docs/hard-enforcement.md`. Passive when no
  policy file exists; fail-closed to "ask" on internal errors.
- Policy schema **1.1**: optional per-capability `match` block (`tools`,
  `command_patterns`, `path_patterns`) — deterministic mapping of tool
  calls to capabilities. Additive; 1.0 policies remain valid. Entries
  without `match` are soft-only.
- `hooks/classifiers.json` — built-in dangerous-action classifiers
  (fs.delete, git.push/history.rewrite, db.destructive, sys.config.change,
  pkg.install, shell.indirect_exec, fs.write.outside_project) routed
  through `defaults.unknown_action`.
- Self-protection: agent modifications of the policy file always `ask`
  (SPEC I-8); truncation of the audit log is denied (SPEC I-6).
- `tests/run_tests.py` — 46 assertions across the decision table, compound
  commands, path escapes, fail-closed paths, and audit records.

### Changed
- `skill/` → `skills/` (plugin auto-discovery; still copyable standalone).
- Audit coexistence protocol: the hook writes execution records and
  touches `.lorm/hook-active`; the skill then writes only verification
  records (`x-verifies`). Rate limits count execution records only.
- `validate_policy.py`: match-block semantic checks; warns on soft-only L5
  entries and non-hook-verifiable Bash targets.

## 2.0.0 — 2026-07-11

First standalone release. LORM v1 existed as an internal manifesto document;
v2 reworks it into a normative specification plus practical tooling.

### Added
- `SPEC.md` — normative core with RFC 2119 requirement language.
- Per-capability level assignment: levels attach to action classes, never to
  whole systems (SPEC §4).
- Trust lifecycle: promotion criteria and mandatory automatic demotion
  triggers (SPEC §6).
- Runtime graceful degradation rules (SPEC §7).
- L5 policy lifecycle: author/approver separation, mandatory expiry,
  tested-before-activation (SPEC §8).
- Composition & arbitration rules for concurrent L4/L5 capabilities (SPEC §9).
- Closed-loop outcome verification and audit record requirements (SPEC §10).
- Human-factors section naming approval fatigue as a failure mode (SPEC §11).
- Machine-readable policy format: `schema/lorm-policy.schema.json` with
  examples.
- Claude Code Agent Skill (`skills/lorm/`) implementing soft LORM enforcement.
- `docs/related-work.md` — positioning vs. Parasuraman–Sheridan–Wickens,
  SAE J3016, TM Forum Autonomous Networks, IBM autonomic computing.

### Changed
- Normative and rationale content separated (`SPEC.md` vs `RATIONALE.md`).
- Terminology standardized on "level" (v1 mixed "layer" and "level").
- The epistemic/authority seam named explicitly: L0–L2 are epistemic levels,
  L3–L5 are authority levels.

### Removed
- Repetitive manifesto passages (moved to `RATIONALE.md`).
