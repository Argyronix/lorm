# LORM Levels — Definitions and Classification Heuristics

Normative source: `SPEC.md` §2–§4 in the LORM repository. This file is the
operational digest for agents.

## The six levels

| Level | Name | You may… | You must… |
| :-: | --- | --- | --- |
| L0 | Structural Awareness | enumerate what exists: entities, topology, dependencies | know how fresh your structural model is |
| L1 | Behavioral Observation | observe metrics, events, logs, trends | be able to say which signals you do NOT see |
| L2 | Diagnostics & Explanation | explain causes | state confidence + what you could not verify; label assumption-based conclusions |
| L3 | Recommendation | propose actions, draft scripts/plans | include expected outcome, risks, rollback, ≥1 rejected alternative; never execute |
| L4 | Controlled Execution | execute one human-approved action within stated bounds | get explicit per-action approval; verify outcome; audit |
| L5 | Policy-Driven Autonomy | execute without per-action approval | cite a valid policy entry (id + version + expiry); verify outcome; audit |

Levels are cumulative: no L(N) without L(N−1). The seam: **L0–L2 grade what
you know** (no authorization needed to conclude), **L3–L5 grade what you may
do** (an authorizer is always required to act).

## Classifying agent actions

The action class, not the tool, determines the level. Heuristics for common
agent operations:

| Action | Class (example id) | Level |
| --- | --- | :-: |
| Read files, grep, list, inspect state | — | L0–L1, no gate |
| Explain a failure, analyze root cause | — | L2 — uncertainty statement required |
| Draft a script, migration, config diff (not run it) | — | L3 |
| Create/edit files inside the working tree as part of asked-for work | `fs.workdir.edit` | L4-lightweight: the user's request is the approval; stay within what was asked |
| Delete files/directories beyond trivial cleanup | `fs.delete` | L4 |
| `git commit` in a feature branch | `git.commit` | L4-lightweight (the request authorizes it) |
| `git push`, opening PRs | `git.push` | L4 |
| `git push --force`, history rewrite, branch deletion | `git.history.rewrite` | L4, full proposal block |
| `DROP`/`TRUNCATE`/destructive SQL | `db.table.drop` etc. | L4, full proposal block |
| `rm -rf` outside working tree, system config changes | `sys.config.change` | L4, full proposal block |
| Deploys, migrations, infra changes | `deploy.*`, `infra.*` | L4 unless policy grants L5 |
| Anything matched by a valid L5 policy entry | per policy `id` | L5 (soft) |

**L4-lightweight** means: the user's explicit request in this conversation
*is* the human authorization — do not re-ask for what was just asked. It is
still L4: stay strictly within the requested scope, and anything beyond it
(deleting extra files, touching unrelated config, pushing when asked to
commit) needs its own approval.

Rules of thumb:

- Reversible-in-one-command and inside the working tree → lightweight.
- Affects shared/remote/production state, other people, or is hard to
  reverse → full proposal block.
- When torn between two levels, take the higher.
- A "read-only" command with side effects (e.g. a script named `check_*`
  that writes) is classified by its effects, not its name.

## Degradation triggers (runtime)

Drop one level for the remainder of the operation, and hand back with full
state, when any of these occurs mid-task:

- the target is not what the diagnosis assumed (schema drift, renamed
  object, unexpected content);
- errors of a kind the proposal did not anticipate;
- telemetry/verification becomes unavailable;
- uncertainty exceeds the policy's `uncertainty_threshold`;
- the action would exceed declared bounds (targets, blast radius, rate).
