# Changelog

The LORM specification follows semantic versioning. The policy schema version
(`lorm_policy` field) is versioned independently of the specification.

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
