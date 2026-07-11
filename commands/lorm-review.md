---
description: Review the LORM trust lifecycle — analyze the audit log and present promotion/demotion drafts for human decision
---

Run the LORM trust-lifecycle review for the current project and present
the results to the user.

1. Execute:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/lorm/scripts/lorm_review.py" "$PWD" --json
```

(If `CLAUDE_PLUGIN_ROOT` is not set in your shell, locate the script under
the installed plugin or `.claude/skills/lorm/scripts/`.)

2. Interpret the JSON and report to the user, in this order:
   - a one-paragraph summary of the capability portfolio (executions,
     verification coverage, current levels);
   - **promotion candidates** — for each, show the evidence and the draft
     L5 policy entry as a reviewable diff against `lorm-policy.yaml`.
     Point out every `DRAFT` placeholder that the human must fill
     (author, approver — they must differ, SPEC 8-1; match patterns;
     targets). Recommend canary scope (SPEC 6-3);
   - **demotion proposals** — show the draft `demotions[]` entries and the
     failures behind them;
   - **expiry warnings** and **hygiene findings** — including low
     verification coverage (the reason a capability cannot be promoted,
     SPEC I-7).

3. LORM I-8 applies to you: you MUST NOT write any of these drafts into
   `lorm-policy.yaml` yourself. Offer the diff; the human applies it (or
   explicitly approves the exact diff and you apply that diff verbatim in
   a separate, visible step).

4. If there are no findings, say so plainly — a steady state is a valid
   result, not a failure.
