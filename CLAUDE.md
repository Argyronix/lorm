# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this repository is

LORM — the Layered Operational Responsibility Model. Two things at once:

1. **A specification** (`SPEC.md`, RFC 2119 language) grading AI-agent
   autonomy L0–L5 by *authorization source* (nobody / human per action /
   written policy), assigned per capability, with earned promotion and
   automatic demotion.
2. **A working Claude Code plugin** implementing it: agent skill
   (`skills/lorm/`, soft layer), enforcement hooks
   (`hooks/scripts/lorm_gate.py` — PreToolUse authorization gate +
   PostToolUse audit writer, hard layer), machine-readable policy schema
   (`schema/`), trust-lifecycle analyzer (`/lorm:lorm-review` command +
   `skills/lorm/scripts/lorm_review.py`).

Public repo: https://github.com/Argyronix/lorm (Apache-2.0). Origin:
extracted from the Argyronix product workspace; the Basis documents there
defer to this repo's SPEC.md as canonical.

## Testing and validation

```bash
python3 tests/run_tests.py            # full suite (subprocess-driven, no pytest)
python3 skills/lorm/scripts/validate_policy.py schema/examples/full.lorm-policy.yaml
python3 skills/lorm/scripts/validate_policy.py schema/examples/minimal.lorm-policy.yaml
```

All tests green is the bar for every engine/schema change. Tests create
temp projects under `$TMPDIR`. Engine changes without a covering test are
not done. For live verification: `claude --plugin-dir . -p "…"` in a
scratch project with a policy file (see docs/hard-enforcement.md §Testing).

## Non-negotiable design invariants

- **Propose, never enact (SPEC I-8).** No tool in this repo — skill,
  hook, analyzer, command — may ever write `lorm-policy.yaml` or grant
  levels. Everything produces drafts for human review. Do not add
  "auto-apply" conveniences.
- **Fail-closed, never crash-open.** Engine errors in the pre path emit
  `ask` with the error; the post path never blocks a completed call.
- **Deny > ask > allow > silence.** Silence hands the call to Claude
  Code's normal permission flow — that is the designed fallback, not a
  bug. The plugin is passive in projects without a policy file.
- **Per-segment Bash evaluation.** Capabilities and classifiers are
  evaluated per shell segment so an allowed segment can't smuggle a
  dangerous sibling (`rm -rf build && rm -rf /`). Don't "optimize" this
  back to whole-command matching.
- **Audit log is append-only** (SPEC I-6): hook denies truncation.
  Hook-vs-skill dedup: the hook writes execution records and touches
  `.lorm/hook-active`; the skill then writes only verification records
  (`x-verifies`). Rate limits count execution records only.
- **No conditions DSL.** Executable conditions are human-authored shell
  `check` commands (schema 1.3), deliberately. If formal evaluation is
  ever needed, integrate OPA — do not invent an expression language.
- **Not a security boundary against an adversarial model** — keep the
  threat-model framing in docs/hard-enforcement.md honest; never claim
  otherwise in docs or reasons.

## Conventions

- Policy schema versions are **additive** (`lorm_policy` "1.0"…"1.3");
  old policies must stay valid. `minimal.lorm-policy.yaml` intentionally
  stays at "1.0" to prove backward compatibility.
- Version discipline: bump `.claude-plugin/plugin.json` and add a
  CHANGELOG entry together; spec (SPEC.md) is versioned separately
  (semver, currently 2.0.0) from the plugin.
- Engine code: stdlib-only; PyYAML imported lazily and only for YAML
  policies (JSON policies must work without it). `classifiers.json` is
  JSON for exactly that reason.
- Glob semantics everywhere are `fnmatch.fnmatchcase`; `*` crosses `/`
  (documented in docs/hard-enforcement.md); a path that is an ancestor of
  a target scope is within scope.
- Terminology: "level" (not "layer"); capability ids are dotted
  `domain.object.verb`; MCP mapping is `mcp__server__tool` →
  `mcp.server.tool`. The retired IM/DM vocabulary must not reappear.
- All content in English. Normative statements only in SPEC.md
  [Normative] sections; docs/ is non-normative except
  hard-enforcement.md, which is normative for the hook.

## Layout notes

- `skills/lorm/` must remain independently copyable (users may
  `cp -r` it into `.claude/skills/` without the plugin) — no imports
  from outside the skill directory.
- `hooks/hooks.json` matcher is `Bash|Write|Edit|mcp__.*` for both
  PreToolUse and PostToolUse; both invoke `lorm_gate.py pre|post`.
- Docs map: user entry point `docs/user-guide.md`; hook contract
  `docs/hard-enforcement.md`; lifecycle tooling `docs/trust-lifecycle.md`;
  positioning `docs/related-work.md`; motivation `RATIONALE.md`.

## Releasing

```bash
python3 tests/run_tests.py                      # must be green
git add -A && git commit && git push origin main # gh CLI is the credential helper
curl -sf https://raw.githubusercontent.com/Argyronix/lorm/main/.claude-plugin/plugin.json
```

Users install via `/plugin marketplace add Argyronix/lorm` →
`/plugin install lorm@argyronix-lorm`; pushing to `main` is releasing.
