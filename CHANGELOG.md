# Changelog

The LORM specification follows semantic versioning. The policy schema version
(`lorm_policy` field) is versioned independently of the specification.

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
- Claude Code Agent Skill (`skill/lorm/`) implementing soft LORM enforcement.
- `docs/related-work.md` — positioning vs. Parasuraman–Sheridan–Wickens,
  SAE J3016, TM Forum Autonomous Networks, IBM autonomic computing.

### Changed
- Normative and rationale content separated (`SPEC.md` vs `RATIONALE.md`).
- Terminology standardized on "level" (v1 mixed "layer" and "level").
- The epistemic/authority seam named explicitly: L0–L2 are epistemic levels,
  L3–L5 are authority levels.

### Removed
- Repetitive manifesto passages (moved to `RATIONALE.md`).
