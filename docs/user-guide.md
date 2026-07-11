# LORM User Guide

*Plain-language introduction, usage scenarios, and example configuration.
For requirements, see [SPEC.md](../SPEC.md); for hook internals,
[hard-enforcement.md](hard-enforcement.md).*

## LORM in plain words

When people talk about AI-agent autonomy, they usually ask "how smart is
it?" or "what can it do?". LORM asks a different question:

> **Who gave it permission?**

Think of a new employee. On day one they can look around and read the
docs (L0–L1). Soon they understand the systems well enough to explain
problems (L2) and suggest fixes (L3). After a while you let them make
changes — but you review each one (L4). Only much later, for *specific,
well-rehearsed tasks*, do you say: "you don't need to ask me for this
anymore" — and you put that in writing, with limits, and you can take it
back the moment something goes wrong (L5).

That's the whole model:

| Level | The agent may… | Who authorizes |
| :-: | --- | --- |
| L0 | know what exists | nobody needed |
| L1 | watch what is happening | nobody needed |
| L2 | explain why (stating what it isn't sure about) | nobody needed |
| L3 | propose actions — never execute | you decide |
| L4 | execute one action you approved | you, each time |
| L5 | execute on its own, within written limits | a policy you signed off |

Three rules make it work in practice:

1. **Trust attaches to specific tasks, not to the agent.** The same agent
   can be trusted to clean build artifacts on its own (L5) while every
   schema change still needs your approval (L4). There is no "the agent
   is now autonomous" switch.
2. **Trust is earned slowly and lost instantly.** A task gets promoted
   after a proven track record; it gets demoted automatically on the
   first failure. Re-earning starts over.
3. **The agent never grants itself anything.** "Do this automatically
   from now on", said in chat, produces a *draft* for you to review —
   never new permissions. Permissions live only in a file you edited.

## The three artifacts

- **`lorm-policy.yaml`** — the permission file, at your project root.
  Everything the agent may do without asking, with limits and expiry
  dates. No file = nothing is pre-authorized; every state-changing action
  needs your approval. You write it; the agent may only propose diffs.
- **`.lorm/audit.jsonl`** — the log. Every gated execution lands here:
  what ran, who authorized it, what the outcome was. Rate limits are
  counted against it, and promotions are earned from it. Append-only —
  the plugin physically blocks attempts to rewrite it.
- **The plugin** (or the copied skill) — the mechanism. The skill makes
  the agent *behave* by LORM (diagnose first, state uncertainty, present
  approval requests); the plugin's hooks make the boundary *physical*
  (valid policy → runs without a prompt; no policy → forced prompt;
  forbidden → blocked).

## Install

```bash
# Full plugin — skill + enforcement hooks (recommended)
/plugin marketplace add Argyronix/lorm
/plugin install lorm@argyronix-lorm

# …or soft layer only: copy the skill into one project
cp -r skills/lorm /path/to/project/.claude/skills/lorm
```

Pick one, not both. Installing the plugin is safe everywhere: in projects
without a policy file, the hooks stay silent.

## Scenario 1 — first day: no policy file

You ask: *"Drop the `old_sessions` table, we don't need it."*

Without LORM the agent would just drop it. With LORM it first inspects
the actual object — row count, last access, who references it — and comes
back with a structured request:

```
LORM L4 approval request — db.table.drop
Action:       DROP TABLE old_sessions
Diagnosis:    0 reads in 90 days, no inbound FKs, 2 stale code refs (listed)
Risk & uncertainty: cannot verify external BI tools that may query it
Alternatives rejected: rename-and-wait 30 days — reversible, safer; flagged
Rollback:     none after drop — irreversible; recommend the rename path
Bounds:       exactly one table
```

You see the full picture *before* the irreversible step, and you answer
"yes", "no", or "do the safer variant". Nothing ran yet — that's the
point of L4.

## Scenario 2 — pressure: "don't analyze, just do it"

Urgency changes the *depth* of diagnostics, never their *existence*. The
agent still spends ten seconds inspecting the target and shows what it
found before the gate. If diagnostics are impossible, it stays at L3 and
tells you what information is missing. (This behavior held up under
direct pressure in our test scenarios.)

## Scenario 3 — approval fatigue, solved honestly

The agent asked "run tests and commit if green?" forty times this month;
you approved forty times. Reflexive approval is the failure mode LORM
names explicitly. The honest fix: the agent (or `/lorm:lorm-review`)
proposes a policy so you decide **once, deliberately**, instead of forty
times, reflexively:

```yaml
# proposed by the agent as a diff — you review and apply it
capabilities:
  - id: git.commit.tested
    description: "Commit to feature branches when the full test suite passes"
    level: L5
    match:
      tools: [Bash]
      command_patterns: ["git commit *"]
    policy:
      version: 1
      author: "you@example.com"
      approved_by: "lead@example.com"   # must be a different person
      approved_at: 2026-07-11
      expires: 2026-10-11               # no immortal permissions
      tested: "40 approved identical executions, 0 reverts"
    conditions:
      - text: "full test suite is green"
        check: "test -f .test-status && grep -q PASS .test-status"
    bounds:
      targets: ["feature/*", "fix/*"]
      blast_radius: { max_objects: 1, max_actions_per_hour: 6 }
    rollback: "git reset --hard HEAD~1 (branch-local)"
    verification:
      expect: "branch CI passes after the commit"
```

## Scenario 4 — autonomous, and accountable

With that policy in place, the agent announces its authority and acts:

> Executing under policy `git.commit.tested` v1 (expires 2026-10-11);
> rate 2/6 this hour; 1 condition check(s) passed.

The hook independently verified all of it — pattern match, expiry,
demotions, rate limit against the log, the condition command — and only
then skipped the permission prompt. One record lands in the audit log:

```json
{"timestamp": "2026-07-11T14:32:07Z", "capability": "git.commit.tested",
 "level": "L5", "authorizer": "policy:git.commit.tested@1",
 "action": "git commit -m 'fix flaky retry test'",
 "params": {"tool": "Bash"}, "diagnosis_ref": "unavailable-to-hook",
 "outcome": "committed 1f2e3d4", "verified": "pending",
 "x-writer": "lorm-hook"}
```

## Scenario 5 — trust is lost instantly, reviewed regularly

A verification fails (the commit broke CI). The capability stops being
autonomous: the failure is a demotion trigger, and `/lorm:lorm-review`
drafts the entry:

```yaml
demotions:
  - capability: git.commit.tested
    from: L5
    to: L4
    reason: "verification failure 2026-08-02 (branch CI red after commit)"
    date: 2026-08-02
    until: "re-promotion per SPEC §6.2"
```

From the moment you apply it, every such commit needs your approval
again. Run `/lorm:lorm-review` on a cadence — it also reminds you of
expiring policies (with the verification summary a renewal needs) and
flags capabilities whose track record is too unverified to ever promote.
Want to revoke *right now* without ceremony? Delete the capability entry
from the policy file — the next action falls back to L4 immediately.

## Scenario 6 — "add yourself a policy"

If you (or anyone) casually tell the agent to grant itself permissions,
it refuses and produces a diff instead — usually a *narrower* one than
asked, with the risks flagged. The plugin backs this up mechanically:
agent writes to `lorm-policy.yaml` are intercepted, and truncating the
audit log is denied outright. In our live tests the agent both refused
the self-grant and had its later attempt to edit the audit log blocked
by the hook with the exact reason.

## A starter policy, annotated

Copy this as `lorm-policy.yaml` and grow it as trust accumulates:

```yaml
lorm_policy: "1.3"

metadata:
  project: "my-project"
  owner: "you@example.com"          # who is accountable for this file
  updated: 2026-07-11

# What happens for actions NOT listed below:
defaults:
  max_level: L3                     # unlisted = recommend-only by default
  unknown_action: escalate          # escalate -> ask you; refuse -> block
  uncertainty_threshold: 0.2

# Start with an empty (or absent) capabilities list: everything
# state-changing is L4 — the agent asks, you approve. Add entries as
# /lorm:lorm-review shows they've earned it.
capabilities: []

audit:
  log: ".lorm/audit.jsonl"
  record_fields: [timestamp, capability, level, authorizer, action,
                  params, diagnosis_ref, outcome, verified]
```

Two ready-made references for the next stage:
[minimal](../schema/examples/minimal.lorm-policy.yaml) (exactly the file
above) and [full](../schema/examples/full.lorm-policy.yaml) (L4 + L5 +
MCP + executable condition + a demotion, all commented). Validate any
edit before relying on it:

```bash
python3 skills/lorm/scripts/validate_policy.py lorm-policy.yaml
```

## FAQ

**The agent stopped mid-task and "handed back". Why?**
Something its plan assumed stopped being true (unexpected file contents,
lost telemetry, errors of an unanticipated kind). LORM requires it to
stop and report state — what's done, what remains, what's now uncertain —
rather than improvise at the same trust level.

**Headless runs (`claude -p`) get blocked on L4 actions.**
By design: no human present means no L4 authorizer. Give the recurring
action class an L5 policy entry — that's the honest fix — or wire a
programmatic approver.

**"policy is YAML but PyYAML is not installed".**
`pip install pyyaml`, or keep the policy as `lorm-policy.json` — JSON
needs nothing.

**The audit log grows forever.**
Rotate by *moving* it aside (`mv .lorm/audit.jsonl .lorm/audit-2026Q3.jsonl`);
rotated files aren't rate-counted. Never truncate in place — the hook
denies that anyway (append-only rule).

**Does this stop a malicious agent?**
No, and it doesn't claim to — see the threat model in
[hard-enforcement.md](hard-enforcement.md). It makes an honest agent's
authorization boundary deterministic and auditable, and it removes the
"the model felt confident today" factor from what runs unprompted.

**Skill only, or full plugin?**
Skill only = discipline (the agent behaves by LORM, nothing physically
stops it). Plugin = discipline + mechanism. If you can install the
plugin, do.
