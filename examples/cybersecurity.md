# LORM Applied: Security Operations

*Non-normative.*

## Security operations portfolio

| Capability | Level | Authorization |
| --- | :-: | --- |
| `sec.assets.inventory` — assets, exposure surface, dependency map | L0 | — |
| `sec.telemetry.observe` — IDS events, auth logs, traffic baselines | L1 | — |
| `sec.threat.attribute` — incident analysis with confidence | L2 | — |
| `sec.remediation.recommend` — containment and patching plans | L3 | human decides |
| `sec.host.isolate` — quarantine a workstation | L4 | analyst, per action |
| `sec.ip.block` — block malicious IPs at the edge | L5 | policy: threat-intel score threshold, max 100 IPs/hour, never internal ranges, expires quarterly |
| `sec.account.disable` — disable a user account | L4 forever | false positives lock out humans; deliberately kept human-authorized |

Security shows the demotion mechanic at its sharpest: one high-profile false
positive on `sec.ip.block` (blocking a partner's NAT gateway) → automatic
demotion to L4, every block hand-approved again until the full re-promotion
path — with the trigger condition fixed and canary-scoped — is walked.

## Other domains

Security is the domain where demotion bites hardest, because false positives are
frequent and their cost is immediate. Two other portfolios are worked through
separately: [clinical operations](medicine.md), where most capabilities correctly
never leave L3 because outcomes verify slowly and errors are irreversible, and
[procurement](procurement.md), where bounds are denominated in money and a
capability that could widen another's bounds is deliberately pinned at L4.
