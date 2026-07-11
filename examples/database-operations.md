# LORM Applied: Database Operations

*Non-normative. The domain LORM originated in.*

## The portfolio view

A database-operations platform is not "an L5 product." It is a portfolio of
capabilities, each at its own earned level:

| Capability | Level | Authorization |
| --- | :-: | --- |
| `db.inventory.scan` — enumerate databases, tables, indexes, topology | L0 | — |
| `db.metrics.observe` — dead tuples, bloat trends, query latency, wraparound age | L1 | — |
| `db.diagnose.*` — root-cause analysis of bloat, stale stats, slow plans (with confidence) | L2 | — |
| `db.recommend.*` — index changes, config tuning, maintenance plans | L3 | human decides |
| `db.index.create` — create approved indexes in bounded targets | L4 | human, per action |
| `db.stats.analyze` — ANALYZE tables with stale statistics | L5 | policy (canary-scoped first) |
| `db.vacuum.run` — plain VACUUM within maintenance windows | L5 | policy |
| `db.table.drop`, GUC changes, blocking operations | L3/L4 forever | structurally ineligible for L5: irreversible or unbounded |

## Level walkthrough

- **L0** — inventory: what databases exist, their schemas, sizes,
  dependencies. Staleness is tracked; a diagnosis against a week-old
  inventory says so.
- **L1** — telemetry: `pg_stat_*` counters, autovacuum activity, transaction
  ID age. The system knows which signals it lacks (e.g. no `pg_stat_statements`
  installed) and says so in diagnoses that would need them.
- **L2** — "table X is bloated because autovacuum cannot keep up with the
  update rate; confidence high; could not verify long-running transactions on
  the standby."
- **L3** — "run VACUUM during the low-traffic window; alternative: tune
  autovacuum cost limits (slower to take effect, less disruptive); do-nothing
  risks reaching the bloat threshold in ~9 days."
- **L4** — the DBA approves that specific VACUUM; the system runs it inside
  the stated window, verifies dead-tuple reduction, writes the audit record.
- **L5** — after N verified L4 executions, the DBA approves a policy:
  `db.vacuum.run` on `prod/analytics_*`, max 3 tables/night, never during
  business hours, expires in 90 days. The system now acts alone — and cites
  the policy every time.

## Trust lifecycle in this domain

Promotion `db.stats.analyze` L4→L5: 122 supervised executions on staging, 0
failures, canary policy on two schemas first, then widened by a new policy
version. Demotion: one night the verification query fails after an ANALYZE
run (table lock contention incident) → the capability drops to L4
automatically; the DBA sees the demotion record in the morning; re-promotion
requires the full path again.

## Composition example

Two L5 loops can collide: bloat remediation wants `VACUUM FULL`-adjacent
maintenance on a table while wraparound protection schedules an aggressive
freeze on the same table. Arbitration: wraparound protection has declared
precedence (data-loss risk beats performance); the bloat loop records that it
yielded and re-fires after the freeze completes.
