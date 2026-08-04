# LORM Applied: Procurement and Supply Chain

*Non-normative.*

Procurement is a useful test of the model because the domain already thinks in
LORM's terms and has for decades — under different names. Spending limits are
`bounds`. Segregation of duties is the author ≠ approver rule. Purchase-order
approval thresholds are per-action human authorization. What the domain does
*not* usually have is an explicit place to record that a class of purchase may
now proceed without asking, under what limits, and until when.

## The portfolio view

| Capability | Level | Authorization |
| --- | :-: | --- |
| `proc.inventory.observe` — stock levels, locations, in-transit quantities | L0 | — |
| `proc.demand.observe` — consumption rates, lead times, seasonality, supplier delays | L1 | — |
| `proc.risk.diagnose` — why a shortfall is coming: demand shift, supplier slippage, port congestion (with confidence) | L2 | — |
| `proc.order.recommend` — what to buy, from whom, when, with cost/risk trade-offs | L3 | human decides |
| `proc.po.create` — raise a purchase order for an approved item | L4 | buyer, per action |
| `proc.replenish.routine` — reorder consumables at known prices from approved suppliers | L5 | policy: listed SKUs, ≤ $5k per order, ≤ $40k/month, approved suppliers only, expires quarterly |
| `proc.supplier.add` — add a new supplier to the approved list | L4 forever | the control that makes every other limit meaningful |
| `proc.payment.release` — release funds | L3/L4 forever | segregation of duties; the system may prepare, never release |

## Why two capabilities are pinned below L5

`proc.supplier.add` and `proc.payment.release` are not held back because they are
technically hard. They are held back because automating them would dissolve the
controls the other limits depend on.

A policy that caps `proc.replenish.routine` at approved suppliers is only as
strong as the approved-supplier list. If the system could extend that list, it
could satisfy its own constraint by widening it — the procurement equivalent of
an agent granting itself permissions, which SPEC I-8 forbids in the policy file
and the same reasoning forbids here. This is a general pattern worth naming: **a
capability that can modify the bounds of another capability inherits the higher
of the two levels, and usually stays at L4.**

Payment release is the same argument in the other direction, and it is why
`author ≠ approver` (SPEC §8) is not bureaucratic decoration. Finance discovered
that rule the hard way, long before software agents existed.

## Trust lifecycle in this domain

Promotion is easy to evidence here, because outcomes verify quickly and cheaply.
`proc.replenish.routine` earns L5 after a quarter of L4 orders where the received
quantity, unit price and lead time matched the expectation recorded with each
approval. That is mechanical verification (SPEC §10) with no judgement call
involved: three fields, compared on delivery.

Demotion is equally concrete. A unit price arrives 30% above the policy's
declared ceiling — verification fails, the capability drops to L4, and every
reorder is hand-approved until the price basis is re-established. Note what the
system does *not* do: it does not decide that the new price is acceptable because
the goods are needed. That judgement was never delegated.

## Where the domain differs from database operations

Rollback is often impossible — goods ship, funds move — but that does not
disqualify L5 the way it would for an irreversible schema change, because the
*blast radius* is bounded in currency rather than in data. A $5,000 cap with a
$40,000 monthly ceiling is a genuine limit on harm, and it is enforceable
mechanically. Where money is the unit of damage, bounds do the work that
reversibility does elsewhere.
