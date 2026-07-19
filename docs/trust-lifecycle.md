# Trust-Lifecycle Tooling — `lorm_review.py` and `/lorm-review`

*Companion to SPEC §6 (promotion/demotion), §8.2 (renewal), §10.4 (trust
record). Non-normative.*

LORM's distinguishing claim is that autonomy is *earned per capability and
lost automatically*. The review tool makes that lifecycle operational: it
turns the audit log — the trust record that the enforcement hook and the
skill accumulate — into concrete, human-decidable transition proposals.

## Run it

```bash
python3 skills/lorm/scripts/lorm_review.py [project_dir] [--json]
        [--window DAYS]     # history considered (default 90)
        [--min-track N]     # verified executions required for promotion (default 10)
```

Or, with the plugin installed: **`/lorm:lorm-review`** — the agent runs the
analyzer and presents the drafts as reviewable diffs.

## What it reports

| Section | Trigger | Output |
| --- | --- | --- |
| **Promotion candidates** | ≥ `min-track` *verified* executions, 0 failures, not demoted, not already L5 (SPEC 6-2/6-3) | Draft L5 policy entry: track record cited in `tested`, expiry +90d, rate limit derived from observed peak (×2), `match`/`bounds` inherited from the existing L4 entry, `DRAFT` placeholders for author/approver |
| **Demotion proposals** | failed verification with no active demotion (SPEC 6-5) | Draft `demotions[]` entry naming the failure |
| **Expiry** | L5 policy expired or expiring ≤ 14d (SPEC 8-2) | Renewal reminder with the verification summary a renewal review needs |
| **Hygiene** | executions ≥ track but verification coverage too low (I-7); recurring approvals with no policy entry; corrupt audit lines | What blocks the lifecycle from progressing, and why |
| **Discovery** (`lorm_discover.py`, 2.6.0+) | recurring *unclassified* actions — calls no capability or classifier ever saw, clustered from `.lorm/observations.jsonl` by normalized shape | Draft capability entry at ≤ L3 (SPEC 4-3) with a derived `match` block and a verification-gap note |

Two properties worth noting:

- **A failing capability is never simultaneously a promotion candidate** —
  demotion wins, and re-promotion restarts the full §6.2 path.
- **Pending ≠ verified.** Executions the skill never verified do not count
  toward the track record; heavy `pending` counts surface as a hygiene
  finding instead of a promotion. This is I-7 applied to the tooling
  itself: unverifiable history earns nothing.

Two mechanisms keep the pending problem from festering silently (both
plugin 2.5.0+): capabilities with schema-1.4 `verification.mechanical`
checks accumulate `verified`/`failed` track record directly from the hook,
with no agent step involved; and when a capability's unsuperseded pending
count reaches 10/25/50/100 with zero verified, the post hook emits a
one-line `systemMessage` — you learn that lifecycle progress has stalled
without having to run this review first.

## Propose, never enact

The analyzer prints drafts; it does not modify `lorm-policy.yaml`, and the
`/lorm-review` command explicitly forbids the agent from applying drafts
without a human-approved diff (SPEC I-8). Every draft carries `DRAFT`
placeholders — author and approver (who must differ, SPEC 8-1) can only be
filled by humans.

## The intended loop

```
hook/skill execute → audit log accumulates → /lorm-review
      → human applies promotion/demotion diffs → policy evolves
      → hook enforces the new levels → …

unclassified calls → observations accumulate → /lorm-review (discovery)
      → human registers the class at ≤ L3/L4 → audit tracking begins
      → verification builds the track record → promotion path above
```

Run it on a cadence (weekly, or before policy renewals). A "steady state"
result is a valid outcome — most reviews should be boring.
