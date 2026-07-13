# Security Policy

LORM is explicitly **not a security boundary against an adversarial model**
(see `docs/hard-enforcement.md`) — the hook is designed to keep an honest
agent's authorization boundary deterministic, not to withstand a model or
user actively trying to defeat it. That said, bugs that break the boundary
even for honest use are security issues and should be reported privately,
not as a public issue. Examples:

- An action classified below L4 executes without the expected prompt.
- An expired, malformed, or otherwise invalid L5 policy entry still
  produces `allow`.
- The audit log (`.lorm/audit.jsonl`) can be truncated or overwritten
  despite the append-only guarantee (SPEC I-6).
- A Bash command smuggles a denied sub-command past per-segment evaluation
  (the class of bug fixed pre-1.0 for `rm -rf build && rm -rf /`).

## Reporting

Please use GitHub's private vulnerability reporting for this repository:
<https://github.com/Argyronix/lorm/security/advisories/new>

If that isn't available to you, email **edwardfish@argyronix.com** with a
description and, if possible, a reproduction (minimal policy file + command).

Please do not open a public issue for a suspected vulnerability until a fix
has shipped.

## Supported versions

This project does not yet maintain parallel release branches — the latest
version on `main` is the only one that receives fixes.

## Response

Best-effort, no fixed SLA — this is maintained outside of a company security
team. You will get an acknowledgment; the timeline for a fix depends on
severity and reproducibility.
