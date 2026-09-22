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
python3 tests/check_versions.py       # version claims in prose vs. their sources
```

All tests green is the bar for every engine/schema change. Tests create
temp projects under `$TMPDIR`. Engine changes without a covering test are
not done. For live verification: `claude --plugin-dir . -p "…"` in a
scratch project with a policy file (see docs/hard-enforcement.md §Testing).

Supported Python is **3.10 through 3.14** — `.github/workflows/tests.yml`
runs the suite on every one of them, so raising the floor or using a newer
language feature means editing that matrix deliberately. (The floor is 3.10
because `validate_policy.py` annotates with `X | None`, evaluated at
definition time; 3.9 reached end of life in October 2025.) Two CI jobs guard
invariants the suite structurally cannot: the policy examples must validate,
and a JSON policy must be enforced in an environment with no PyYAML at all.
Third-party actions in that workflow are pinned by commit SHA, not tag —
trusting a movable name is the shortcut this project argues against. When
re-pinning, resolve the tag (`git ls-remote`) *and* read `runs.using` in the
action's `action.yml`: a current tag can still target a deprecated Node
runtime, which the runner then forces onto the new one, warning once per job.

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
  Hook-vs-skill dedup: the hook writes execution records, and the **pre**
  path creates `.lorm/hook-active` on the first gated call so the marker is
  already there when the skill checks it in the same turn; the skill then
  writes only verification records (`x-verifies`). Rate limits count
  execution records only. Moving the marker back to the first audit append
  reintroduces the 2.7.1 duplicate-record race — don't.
- **No conditions DSL.** Executable conditions are human-authored shell
  `check` commands (schema 1.3), deliberately. If formal evaluation is
  ever needed, integrate OPA — do not invent an expression language.
- **Not a security boundary against an adversarial model** — keep the
  threat-model framing in docs/hard-enforcement.md honest; never claim
  otherwise in docs or reasons.

## Conventions

- Policy schema versions are **additive** (`lorm_policy` "1.0"…"1.5");
  old policies must stay valid. `minimal.lorm-policy.yaml` intentionally
  stays at "1.0" to prove backward compatibility.
- Version discipline: bump `.claude-plugin/plugin.json` and add a
  CHANGELOG entry together; spec (SPEC.md) is versioned separately
  (semver, currently 2.0.2) from the plugin. Three version lines exist and
  drift apart easily — plugin (`plugin.json`, currently 2.7.2), spec
  (`SPEC.md`), policy schema (`lorm_policy`) — so when one changes, check
  what README.md's "Status and roadmap" claims about all three.
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

## Branch protection

`main` is governed by a repository ruleset — id `20127869`, "main: no deletion
or force-push, PR with code-owner review and CI" — not classic branch
protection. The two briefly coexisted after `engineering` got Write access;
classic protection was removed once its rules were folded into the ruleset so
there is one place to look, not two. Cite the **id** when it matters: names get
edited, and this one already lagged its contents once.

Rules on the ruleset: `deletion` and `non_fast_forward` (no deleting or
force-pushing `main`); `pull_request` (1 approving review, dismiss stale
reviews on push, `require_code_owner_review: true` — the mechanism that
makes `.github/CODEOWNERS` matter, since GitHub won't let an author approve
their own PR, so a `SPEC.md` change by one maintainer needs the other);
`required_status_checks` naming every `tests.yml` job by its `name:` field,
verbatim:

```
suite (Python 3.10) … suite (Python 3.14)
version claims agree
policy examples validate
JSON policy works without PyYAML
```

If a job's `name:` changes, update this list in the same change — an
unmatched context leaves PRs waiting forever on a check that will never
report.

`bypass_actors` grants the `maintainers` team (`EddFish`, `leofrid`) an
`always` bypass — that is what keeps the direct `git push origin main` in
Releasing below working. Everyone else, including `engineering` (Write
access to push branches, not to bypass rules on `main`), must go through a
PR that clears review and CI.

So the code-owner guarantee above holds for **changes that arrive as a pull
request**, which is every change except a maintainer's direct push. A
maintainer pushing `SPEC.md` straight to `main` gets no review at all. That is
the price of keeping the release flow, and it is deliberate — but it means the
four-eyes property on normative text is a convention between the two
maintainers, enforced by the tooling only when they choose to use it. Deletion
and force-push have no bypass and are enforced against everyone.

Both rulesets belong to this repository, not to the organization: org-level
rulesets need a paid GitHub plan, and the Argyronix organization is on the free
one (`GET /orgs/Argyronix/rulesets` answers "Upgrade to GitHub Team"). So there
is nothing to inherit — a second repository, when the open-source client lands
on GitHub, will start with no protection at all and needs its own rules copied
across. Update them with `PUT` on `/repos/{owner}/{repo}/rulesets/{id}`; `PATCH`
is not a route there and answers 404, which reads like a permissions problem and
is not one.

Tags have their own ruleset — id `20127986`, "v* tags: no deletion or
force-push", targeting `refs/tags/v*` with `deletion` and `non_fast_forward`
and no bypass. It is what makes "one tag per version, on the commit that cut
it" enforceable rather than aspirational: a published version reference cannot
be moved to point somewhere else, which is the property the DOIs and the
`Validated against:` lines in other repositories depend on.

Two ruleset settings are deliberately off. `strict_required_status_checks_policy`
is `false`, so CI is not required to have run against the *merge result* — a
branch can pass, sit while `main` moves, and merge untested-in-combination. At
this traffic that trade is worth the absence of rebase churn; revisit it if two
people start landing changes on the same day. `require_last_push_approval` is
`false`, which `dismiss_stale_reviews_on_push` already covers for the case that
matters.

## Releasing

Users install via `/plugin marketplace add Argyronix/lorm` →
`/plugin install lorm@argyronix-lorm`. A **new** install takes the current
state of `main`, so pushing to `main` is what reaches new users. An
**existing** install does not: `plugin.json` sets an explicit `version`,
which pins it, and `/plugin update` reports "already at the latest version"
until that field changes. So a docs-only push reaches new installs and nobody
else — which is the intended behavior, and the reason the version bump is the
real release event even though nothing is distributed by the tag.

Tags and releases do not distribute anything either; they exist so a version
can be rolled back to, cited, and seen.

```bash
python3 tests/run_tests.py                      # must be green
python3 tests/check_versions.py                 # prose claims match the sources
git add -A && git commit && git push origin main # gh CLI is the credential helper
curl -sf https://raw.githubusercontent.com/Argyronix/lorm/main/.claude-plugin/plugin.json
git tag v<version> <the version's commit>       # lightweight, `v` prefix
git push origin v<version>
gh release create v<version> --latest --notes-file <notes>   # newest only
```

Conventions to keep:

- **`v` prefix, lightweight tags.** `plugin.json` and the CHANGELOG headings
  carry the bare number; the tag carries `v`. Lightweight because an
  annotated tag would stamp its own date, and the nine historical tags
  (v2.0.0…v2.6.0) were created retroactively on 2026-07-30 — a tag date
  would have been a false one. The commit date is the real date.
- **One tag per version, on the commit that cut it** — not on whatever
  `main` happens to be. Docs-only and CI-only commits do not get tags,
  because they do not bump `plugin.json`.
- **Release notes live in the release, not in a tracked file.** The full
  change description is already in `CHANGELOG.md`; a second copy in the repo
  would drift. The release body summarizes and links there.
- **Only the newest version gets a GitHub Release object.** Older versions
  stay as tags: GitHub lists them with their commit dates, whereas ten
  release objects would all carry the date they were created.
- Tags are unsigned for now. If commit signing is ever set up, sign tags in
  the same change — a mix of signed and unsigned tags says less than either.
