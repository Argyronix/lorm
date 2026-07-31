# Contributing to LORM

Thank you for looking. This project is small and deliberately opinionated, so
the fastest way to have a change accepted is to know what it will and will not
accept before writing code.

## What this repository is

Two things at once: a **normative specification** (`SPEC.md`, RFC 2119
language) and a **working Claude Code plugin** that implements it (agent skill,
enforcement hooks, policy schema, trust-lifecycle analyzer). They are versioned
separately and reviewed differently.

## Where pull requests are welcome

| Area | How to contribute |
| --- | --- |
| `hooks/` — enforcement engine, classifiers | Pull request, with a covering test |
| `tests/` | Pull request |
| `docs/`, `README.md` | Pull request |
| `examples/`, `schema/examples/` | Pull request |
| `schema/lorm-policy.schema.json` | Pull request, additive changes only (see below) |
| **`SPEC.md`** | **Open an issue first.** Do not send an unsolicited pull request |

`SPEC.md` is normative and cited by other documents. A change to it is a change
to what the model *means*, which needs agreement before it needs wording — so
please argue the case in an issue, and a pull request follows if we agree. This
is not a formality: a well-written pull request against normative text is still
likely to be closed if the change was never discussed.

Bug reports and feature requests use the
[issue templates](.github/ISSUE_TEMPLATE). Security reports go through
[`SECURITY.md`](SECURITY.md), never a public issue or pull request. Questions
are answered per [`SUPPORT.md`](SUPPORT.md).

## Running the checks

Python 3.10 through 3.14 are supported and all are exercised in CI. The engine
needs the standard library only. PyYAML is required to read YAML policy files;
`jsonschema` is required by the validator.

```bash
python3 tests/run_tests.py                  # the suite — must be green
python3 tests/check_versions.py             # version claims vs. their sources
python3 skills/lorm/scripts/validate_policy.py schema/examples/full.lorm-policy.yaml
python3 skills/lorm/scripts/validate_policy.py schema/examples/minimal.lorm-policy.yaml
```

An engine change without a covering test is not finished. Tests drive
`hooks/scripts/lorm_gate.py` as a subprocess with a hook payload on stdin and
assert on the decision, which is also the cheapest way to understand the
engine — read `tests/run_tests.py` before changing behavior.

CI additionally checks two invariants the suite structurally cannot: that both
example policies validate, and that a JSON policy is enforced in an environment
with no PyYAML installed at all.

## Design invariants

These are not preferences. A pull request that breaks one will be declined even
if the code is good, so please raise an issue if you think one should change.

- **Propose, never enact** (`SPEC` I-8). No tool in this repository — skill,
  hook, analyzer, command — may write `lorm-policy.yaml` or grant a level.
  Everything produces drafts for a human to review. Please do not add
  "auto-apply" conveniences: the whole point of the model is that authority has
  exactly two sources, a human decision or a written policy, and a tool that
  writes its own permissions is neither.
- **Fail closed, never crash open.** An engine error on the pre path emits
  `ask` carrying the error. The post path never blocks a call that already ran.
- **Deny > ask > allow > silence.** Silence hands the call back to Claude
  Code's normal permission flow. In a project with no policy file the hooks are
  passive by design — that is the intended fallback, not a gap to close.
- **Per-segment Bash evaluation.** Capabilities and classifiers are evaluated
  per shell segment, so an allowed segment cannot smuggle a dangerous sibling
  (`rm -rf build && rm -rf /`). Do not optimize this into whole-command
  matching.
- **The audit log is append-only** (`SPEC` I-6). The hook denies truncation.
- **No conditions DSL.** Executable conditions are human-authored shell `check`
  commands, deliberately. If formal evaluation is ever needed the answer is to
  integrate OPA, not to invent an expression language.
- **Stdlib only in engine code.** PyYAML is imported lazily and only for YAML
  policies; JSON policies must work with no third-party package installed. That
  is why `classifiers.json` is JSON.
- **Not a security boundary against an adversarial model.** The threat model in
  [`docs/hard-enforcement.md`](docs/hard-enforcement.md) is honest about this.
  Please do not add documentation or reason strings that claim otherwise.

## Schema changes

Policy schema versions are **additive**. Every policy valid under an earlier
`lorm_policy` version must stay valid: add optional fields, never repurpose or
remove existing ones. `schema/examples/minimal.lorm-policy.yaml` intentionally
stays at version 1.0 to prove that backward compatibility, so leave its version
alone.

## Pull request conventions

- All file content in English — code, comments, commit messages, docs, tests.
- One topic per pull request. Say what changed and why in the description; if
  behavior changed, show the before and after decision.
- Do not bump `.claude-plugin/plugin.json` or add a `CHANGELOG.md` entry. The
  maintainer cuts releases, and a version bump in a pull request only creates
  conflicts. Describe the change and it will be folded into the next release.
- Terminology: "level", never "layer". Capability ids are dotted
  `domain.object.verb`. The retired IM/DM vocabulary must not reappear.
- Normative statements belong only in `SPEC.md`. `docs/` is non-normative,
  except `docs/hard-enforcement.md`, which is normative for the hook.

## Licensing of contributions

The project is Apache-2.0. Under section 5 of that license, a contribution you
deliberately submit for inclusion is licensed on the same terms unless you state
otherwise. There is no separate contributor licence agreement to sign, and no
sign-off is required — one less barrier between you and a fix.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
