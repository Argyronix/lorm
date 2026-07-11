# Changelog

The LORM specification follows semantic versioning. The policy schema version
(`lorm_policy` field) is versioned independently of the specification.

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
