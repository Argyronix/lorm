# LORM Applied: AI Coding Agents

*Non-normative. The domain the `skill/lorm` Agent Skill targets.*

## Why coding agents need this

A coding agent's tool set is uniform — run a command, edit a file — but the
*action classes* behind those tools span the entire risk spectrum, from
`grep` to `git push --force` to `DROP TABLE`. Permission systems that gate
tools rather than action classes either prompt constantly (and train the
human to approve reflexively) or grant blanket bypasses. LORM classifies the
action, not the tool.

## The portfolio for a typical coding agent

| Action class | Level | Notes |
| --- | :-: | --- |
| read / search / inspect | L0–L1 | ungated |
| explain failures, review code | L2 | uncertainty stated |
| draft diffs, migrations, scripts | L3 | producing ≠ running |
| edit files in-tree per the user's request | L4-lightweight | the request is the approval |
| `git commit` on a branch | L4-lightweight | |
| `git push`, opening PRs | L4 | proposal block |
| deletions beyond trivial cleanup, force-push, prod-touching commands | L4 | full proposal block |
| `npm audit fix` in CI sandbox nightly | L5 | only via policy file, canary first |

## The L4→L5 bridge (approval fatigue, solved honestly)

Session logs show the agent asked "run the test suite and commit if green?"
40 times this month; the human approved 40 times. Two honest options exist:
keep the approvals real, or make the delegation real. LORM picks the second
without losing the human: the agent *proposes* a policy —

```yaml
- id: git.commit.tested
  description: "Commit to feature branches when the full test suite passes"
  level: L5
  policy:
    version: 1
    author: "agent-proposed, edited by edward"
    approved_by: "teamlead@example.com"
    approved_at: 2026-07-11
    expires: 2026-10-11
    tested: "40 approved identical executions, 0 reverts, June–July 2026"
  conditions:
    - "full test suite green in this session"
    - "branch is not main/release-*"
  bounds:
    targets: ["feature/*", "fix/*"]
    blast_radius: { max_objects: 1, max_actions_per_hour: 6 }
  rollback: "git reset --hard HEAD~1 (branch-local)"
  verification:
    expect: "CI pipeline on the branch passes after push of the commit"
```

— and the human approves the diff once, deliberately, instead of 40 times,
reflexively. The agent never writes this entry itself (I-8).

## Degradation in a coding session

Mid-refactor, the agent discovers the module it is editing is generated code
(a precondition failure: the diagnosis assumed hand-written source).
Conformant behavior: stop editing, report — "3 files edited (list), 2
remaining, the target turned out to be generated from `schema.proto`;
editing the generator instead would be the correct action; nothing pushed" —
and wait. Non-conformant: silently continuing, or an unexplained "task
failed."
