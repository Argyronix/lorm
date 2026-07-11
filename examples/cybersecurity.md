# LORM Applied: Security Operations and Other Domains

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

## Other domains, compressed

| Level | Medicine | Supply chain |
| :-: | --- | --- |
| L0 | patient records | inventory awareness |
| L1 | vitals, lab results | demand and logistics signals |
| L2 | diagnosis (with confidence) | supply-risk analysis |
| L3 | treatment recommendation | procurement recommendation |
| L4 | supervised treatment execution | approved purchasing |
| L5 | closed-loop devices within tight clinical policy (insulin pumps) | auto-replenishment within budget/quantity limits |

Both illustrate SPEC §14: in medicine, most capabilities correctly *never*
pass L3/L4 — not because the models are weak, but because outcomes are hard
to verify quickly and errors are irreversible (I-7). An honest LORM portfolio
in a hospital has a large L2–L3 estate and an L5 set measured in single
digits.
