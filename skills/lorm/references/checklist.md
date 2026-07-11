# LORM Validation Checklist — Agent Form

Normative source: `SPEC.md` §12. Run this before any L3+ output; items 9–14
gate L4/L5 execution. Each item has a pass criterion — if you cannot state
the answer concretely, the item fails and you stop at the highest level whose
items all pass.

| # | Check | Passes when you can state… |
| :-: | --- | --- |
| 1 | Level & scope | the action class id and the level you are requesting, and what is explicitly out of scope |
| 2 | Structural knowledge (L0) | which entities/dependencies this touches, verified against current state — not remembered from earlier in the session |
| 3 | Observations (L1) | which live signals your reasoning uses, and which relevant signals you do NOT have |
| 4 | Diagnosis (L2) | why the action is warranted, traced to actual observations; assumption-based links labeled as such |
| 5 | Uncertainty | what you could not verify, in one honest list |
| 6 | Confidence gate | your confidence, and that it clears the threshold (policy `uncertainty_threshold` or your stated one); below it → degrade and escalate |
| 7 | Action inventory | exactly what will run — commands/SQL/API calls, in full, no placeholders left to improvise |
| 8 | Outcome & verification | the expected outcome and how you will check it afterwards (§10.1); no check possible → say "unverifiable", which blocks L5 |
| 9 | Authorizer | who authorizes: the human (name the approval you will request) or the policy (id + version + expiry) |
| 10 | Disagreement path | what happens on "no" — a coercion-free stop; nothing is half-executed while waiting |
| 11 | Bounds & rollback | targets, blast radius, rate limits, and the concrete rollback (or declared irreversibility) |
| 12 | Auditability | where the audit record goes and that you can fill every required field |
| 13 | Explainability | why act, why alternatives were rejected, why this is safe — *now*, not reconstructed later |
| 14 | Composition | no other autonomous process (cron, CI, another agent, autovacuum-like loops) acts on the same target concurrently; if unknown, say so in Risk |

Practical short form for routine L4-lightweight actions (in-tree edits,
commits): items 1, 2, 7, 11 — the rest are satisfied by the conversation
context. Any full-block L4 or any L5 action: all 14.
