# Related Work and Positioning

*Non-normative. Expands SPEC.md Appendix A.*

Layered autonomy scales have been formalized repeatedly, in several domains,
over five decades. LORM stands on that lineage deliberately. This document maps
the predecessors, states precisely what LORM adds, and addresses the confusion
that causes the most trouble in practice: **the same level number means
different things in different frameworks.**

## The frameworks at a glance

The load-bearing column is the last one. Frameworks that look alike — six
levels, L0 through L5 — diverge on what those levels actually grade, and that is
where every cross-framework misreading starts.

| Framework | Author / owner | Domain | Published | Levels | What the levels grade |
| --- | --- | --- | --- | :-: | --- |
| **LORM** | Argyronix (open specification) | Operational systems; database operations is the origin, the model is engine-agnostic | 2026 | 6 (L0–L5) | **Who authorized the action**, per capability |
| Sheridan–Verplank; **Parasuraman–Sheridan–Wickens (PSW)** | Academia (HCI, aviation) | Human–automation interaction | 1978 / 2000 | 10 levels × 4 functions | Degree of automation, independently per function |
| **SAE J3016** | SAE International | Driving automation | 2014, current revision 2021 | 6 (L0–L5) | Driving capability within an Operational Design Domain |
| **IBM Autonomic Computing** | IBM | IT operations | 2001 | 5 (Basic → Autonomic) | Organizational and technological *maturity* of self-management |
| **TM Forum Autonomous Networks** | TM Forum (industry association) | Telecom networks | 2019 | 6 (L0–L5) | Allocation of operational acts to People vs. Systems, per scenario |
| **Levels of Autonomy for AI Agents** | Feng, McDonald & Zhang (Knight First Amendment Institute) | LLM agents | 2025 | 5 (L1–L5) | The **user's** role, from operator to observer |
| **Data Agents** | Luo, Li, Fan & Tang (SIGMOD tutorial) | LLM data agents | 2026 | 6 (L0–L5) | Agent capability and self-direction, modeled on SAE J3016 |
| **Agency levels** | Hugging Face (`smolagents` documentation) | LLM agent code patterns | living documentation | 6 patterns, 0–3★ | Code-level agency of the agent |
| **NIST ALFUS** | NIST | Robotics, unmanned systems | 2004–2008 | 3 axes | Human independence × mission complexity × environmental complexity |

Two are LORM's nearest relatives. **PSW** is the closest structural ancestor:
automation level is set per *function*, not per system, which reappears in LORM
as per-capability assignment. **TM Forum** is the closest industrial relative:
graded per operational scenario, with the human located explicitly in the loop.

## Predecessor frameworks

### Sheridan–Verplank (1978) and Parasuraman–Sheridan–Wickens (2000)

The founding academic line. Sheridan and Verplank defined a 10-point scale of
automation whose endpoints are "the computer offers no assistance, human must
take all decisions and actions" and "the computer decides everything, acts
autonomously, ignores the human." It is specifically a scale of *decision and
action selection*. Parasuraman, Sheridan & Wickens (*A Model for Types and
Levels of Human Interaction with Automation*, IEEE Transactions on Systems, Man,
and Cybernetics — Part A, 30(3):286–297, 2000) generalized it into a matrix:
automation applies independently to four classes of function — **information
acquisition, information analysis, decision and action selection, action
implementation** — each at its own level.

The four PSW functions map onto LORM's levels almost one-to-one:

| PSW function | LORM level(s) |
| --- | :-: |
| Information acquisition | L0–L1 |
| Information analysis | L2 |
| Decision and action selection | L3 |
| Action implementation | L4–L5 |

What PSW does not have is the authorization axis: its levels grade *how much*
the machine does, not *who delegated the authority*.

### SAE J3016 (driving automation)

The namesake of the L0–L5 notation, and of every "levels of autonomy" analogy
since. SAE grades the driving capability of the vehicle under specified
conditions — the Operational Design Domain. LORM borrows the notation and the
ODD idea (`bounds`, SPEC §8.3) but not the axis: an SAE level says what the car
can do; a LORM level says who authorized the action class.

Worth noting for anyone writing about autonomy: J3016 **deprecates the word
"autonomous"** (clause 7.1.1), along with "self-driving," "unmanned" and
"robotic," on the grounds that the term was "casually broadened … thereby
becoming synonymous with automated," and that even the most advanced systems
"are not self-governing." The deprecation dates from at least the 2018 edition
and is retained in the current 2021 revision — it is a standing position, not a
change made in 2021.

### IBM Autonomic Computing (2001)

The direct ancestor for IT operations. IBM's initiative (Paul Horn's manifesto,
October 2001) defined a control loop over Monitor, Analyze, Plan, Execute and
shared Knowledge — named MAPE-K in IBM's 2005 architectural blueprint — and a
five-step deployment ladder: Basic → Managed → Predictive → Adaptive →
Autonomic. Those stages parallel L1→L2→L3→L4/L5, and the ladder parallels the
trust progression. LORM differs in granularity — per capability, not per
organization — and in making demotion a first-class, automatic mechanism. The
autonomic-computing literature is mostly silent on how autonomy is *withdrawn*.

### TM Forum Autonomous Networks (2019)

The nearest industrial relative. TM Forum classifies telecom operations from L0
(manual) to L5 (full autonomous network) and assesses each *operational
scenario* — "a use case that combines an operation flow and a network domain" —
across five dimensions: Intent/Experience, Awareness, Analysis, Decision,
Execution. Each dimension at each level is assigned to People, Systems, or both
(`P`, `S`, `P/S`). The levels methodology is published as IG1252, the framework
as IG1218.

Two commitments are shared with LORM: grading per scenario rather than per
system, and locating the human explicitly in the loop structure. The
differences: TM Forum's ladder is a target architecture for one industry, human
intent persists into the upper levels, and the framework describes states rather
than transitions.

The industry data calibrates how far anyone actually is. In TM Forum's June 2025
regional survey — 141 respondents across 91 communications service providers —
the distribution of self-reported levels was L0 12%, L1 36%, L2 31%, L3 17%,
**L4 4%**, with **85% targeting L4 by 2030** and L3 the target for 2026. The
instrument offered L0–L4 only; L5 was not an answer option, so no self-reported
L5 figure exists. TM Forum discounts its own L4 respondents explicitly: "it is
likely these respondents were referring to a single domain or process where they
have achieved Level 4, rather than giving an average across their whole network
operations."

That caveat is the more useful finding for LORM's purposes. A single number for a
whole operator is the wrong shape of answer, for exactly the reason SPEC §4 gives:
levels attach to capabilities, not to organizations. TM Forum arrives at the same
observation from the other direction — "different functions within network
operations are at different levels."

A newer benchmark exists (*Assessing CSPs' progress towards Level 4 autonomous
networks*, 18 March 2026, 125 respondents at 80 companies), but its level
distribution is not published outside the gated report; trade coverage reports
21% at L3 or above. The 2025 figures above are cited because they come from an
openly downloadable TM Forum PDF and can be checked.

### AI-agent autonomy taxonomies (2025–)

A fast-growing family. Feng, McDonald & Zhang's *Levels of Autonomy for AI
Agents* (Knight First Amendment Institute, 2025) grades the **user's** role
across five levels: operator, collaborator, consultant, approver, observer. The
*Data Agents* hierarchy (Luo, Li, Fan & Tang, SIGMOD 2026 tutorial) grades agent
capability and self-direction on an explicitly SAE-modeled L0–L5, where L4
agents discover their own tasks and L5 agents are "generative data scientists"
that invent methods. Hugging Face's `smolagents` documentation rates agent code
patterns on an "agency level" scale of up to three stars, across six named
patterns.

These are complementary to LORM rather than competing with it: they grade the
agent's capability or the human's conversational role, while LORM grades the
*action classes* the agent is allowed to touch — and supplies the artifact (the
policy) that makes any of those scales operationally enforceable.

### NIST ALFUS

Autonomy Levels for Unmanned Systems takes a different shape entirely: not one
ladder but three axes — human independence, mission complexity, environmental
complexity — which NIST states can be applied together or independently. It is a
useful reminder that a single-dimensional scale is a simplification, and that a
system "at L4" in one environment may be nowhere near it in another. LORM
handles this through `bounds` rather than a second axis: the same capability that
is L5 inside its declared limits is L4 outside them.

### Self-driving databases

In database operations specifically — LORM's domain of origin — leveled
taxonomies have begun to appear. Postgres.AI's *Self-Driving Postgres*
(Samokhvalov, July 2025) applies an explicitly "SAE J3016-inspired, simplified"
L0–L5 scale to each of 25 identified areas of database operations (vacuum,
bloat, indexes, configuration…), grading degree of automation rather than
authorization; it specifies no delegation artifact and no promotion or demotion
lifecycle, and states a current goal of "levels 3–4 in each of these areas."

Oracle markets Autonomous Database through the self-driving-car analogy and
qualitative self-managing / self-securing / self-repairing claims rather than a
specified level model; the only 0–5 level chart published on oracle.com appears
in a sponsored analyst white paper, without level definitions or authorization
semantics. The academic self-driving-DBMS line (Pavlo et al., *Self-Driving
Database Management Systems*, CIDR 2017) defines its requirements purely as
capabilities — select actions, choose when to apply them, learn from them — with
authorization out of scope and the human present only as a fallback.

The leveled-*notation* niche in this domain is now occupied. The
authorization-axis niche is not.

## Layer-by-layer alignment

The frameworks do **not** align one-to-one, because they grade different axes.
What they share is a skeleton — a sequence of stages that every wave since 2001
rediscovers: execution automates first; sensing and diagnosis follow; the
decision-authority handoff is the pivotal, trust-limited transition everywhere;
goal-setting shifts last, if ever.

The table aligns each framework against that skeleton, using LORM's levels as
the reference spine. Read it as rough correspondence, not equivalence.

| Shared stage | LORM | SAE J3016 | TM Forum | IBM Autonomic | Data Agents | Feng (user role) |
| --- | --- | --- | --- | --- | --- | --- |
| Know what exists | **L0** Structural Awareness | prerequisite, not leveled | Awareness dimension | Basic (monitor) | L0/L1 | — |
| Observe behavior | **L1** Behavioral Observation | prerequisite | Awareness dimension | Managed | L1 | Operator |
| Diagnose, explain | **L2** Diagnostics & Explanation | prerequisite | Analysis dimension | Predictive | L2 partial | Collaborator |
| Recommend | **L3** Recommendation | L1–L2 assistance | Decision dimension; L3 | Predictive → Adaptive | L3 | Consultant |
| Execute with approval | **L4** Controlled Execution | L3 conditional | **L4** | Adaptive | L3 → L4 | **Approver** |
| Act under delegated authority | **L5** Policy-Driven Autonomy | L4 high | L4 → L5 | Autonomic | L4 | Observer |
| Discover own tasks, invent methods | *out of scope — L5 stays human-bounded* | L5 full | L5 (Intent dimension passes to Systems) | — | **L4–L5** (task discovery, then generative) | — |

## The numbering trap

The most important consequence of the table above: **a bare level number is not
portable.** Two examples, running in opposite directions:

- **LORM L5 ≈ TM Forum L4.** LORM is one level "later" because knowing,
  observing and diagnosing are explicit levels here, whereas TM Forum spreads
  those across dimensions instead of levels.
- **IBM's own "Level 3" is LORM's L3–L4 boundary.** In IBM's autonomic
  deployment model the third rung, Predictive, is defined as "system monitors,
  correlates and recommends actions / IT staff approves and initiates actions" —
  a recommendation the human then executes. Two decades later the same
  numbering reappears in IBM's Db2 Genius Hub announcement, whose URL is labeled
  "level 3 automation" while its text describes agents that "propose and execute
  database operations with user approval" — which is LORM **L4**. IBM has
  published no named autonomy scale for Db2; the level numbering there is
  reported by analysts, not defined in IBM documentation.

So: never cross-quote a bare "L4" without naming the framework, and when
comparing two systems' claimed levels, compare what each framework grades first.
The numbers are labels, not measurements.

## What L5 means — the deepest difference

LORM's L5 is deliberately *bounded*: humans author the policies, the system
executes only action classes enumerated in advance, and it never generates its
own goals. L5 is delegated authority — narrower than a human operator's, not
broader. That is a design stance, and it is where LORM parts company with its
relatives most sharply.

| Question | LORM L5 | SAE / Postgres.AI L5 | Data Agents L4–L5 |
| --- | --- | --- | --- |
| What is graded? | Who authorized the action | How little the human is involved | What the agent is capable of |
| Delegation artifact? | **Required** — versioned, expiring policy | None specified | Not a level property |
| May the system set its own goals? | **No** — human-authored policy only | Unspecified | **Yes** — task discovery at L4, method invention at L5 |
| How is autonomy withdrawn? | **Automatic demotion, plus expiry** | Unspecified | Unspecified |

TM Forum sits between these: at L5 the Intent/Experience dimension passes to
Systems across all scenarios, but TM Forum's own definition of intent is
externally given — "the formal specification of all expectations … **given to** a
technical system" — so its top level is not documented as the network inventing
its own objectives.

When one framework says "L5" and another says "L5," they are frequently not
disagreeing about a number. They are describing different endpoints.

## What LORM adds

1. **The authorization axis.** Predecessors grade capability or task-sharing;
   LORM grades the source of authority: none needed (L0–L2), human proposal
   review (L3), human per-action approval (L4), explicit versioned policy (L5).
   The question is never "can the system act?" but "who delegated the authority
   to act?" A system technically able to act but lacking authorization is L3,
   however sophisticated.
2. **The policy as a first-class artifact.** Delegation is legitimate only when
   captured in a reviewable, versioned, *expiring*, tested document with
   separated author and approver (SPEC §8). Informal permission — "just stop
   asking me" — is explicitly not a policy. No predecessor framework specifies
   the delegation artifact at all.
3. **The trust lifecycle.** Promotion is earned per capability on measured
   outcomes, one level at a time; demotion is automatic and immediate on defined
   triggers — incident, rollback, verification failure, telemetry loss, policy
   expiry (SPEC §6). Predecessor frameworks are static ladders describing states;
   they are largely silent on the downward direction.
4. **Runtime degradation with stateful handback** (SPEC §7). When a level's
   preconditions fail mid-operation, the capability drops a level and hands back
   *with state*: what was done, what remains, what is now uncertain. This imports
   the aviation lesson that the handover moment is the most dangerous part of
   high automation.
5. **Named human-factors failure modes.** Approval fatigue at L4 is called out as
   a defect, with countermeasures (SPEC §11), rather than assuming the human
   control is real because a human is present.

## Cautions that apply to LORM too

A 2025 systematic review of 36 papers on levels of autonomy (Richardson, Fidock
& Gunawan, *International Journal of Human–Computer Interaction*) finds
"conceptual confusion between automation and autonomy" running through the
literature, alongside misinterpretation of the taxonomies and methodological
problems in how they are built. LORM's axis is authorization rather than
automation, which addresses that specific confusion directly — but the review is
a caution about the genre, and LORM is in the genre.

Two habits to avoid, both of which LORM's structure discourages and its
*readers* nonetheless fall into:

- **"We are at L4" is a category error.** A portfolio has levels; a system does
  not. Levels attach to capabilities (SPEC §4), so the honest form is "these
  three capabilities are at L4, the rest are L2–L3."
- **A higher number is not progress.** If a capability never needed autonomy —
  because its outcome cannot be verified quickly, or its errors are
  irreversible — then leaving it at L3 forever is the correct answer, not a
  failure to advance.

One more pattern worth carrying over from the other domains: **autonomy arrives
narrow-first.** Wherever a field crosses the decision-authority pivot, it does so
with a bounded scope — SAE's ODD, TM Forum's per-scenario grading, LORM's canary
policy scope. "Full autonomy everywhere" is a label, never a launch.

## Honest positioning statement

The ladder is not new, and LORM does not claim it is. TM Forum built nearly the
same ladder for networks; PSW built the matrix behind it in 2000; SAE made the
notation famous. LORM's claim is narrower and stronger: it moves the grading axis
from capability to delegated authority, attaches the lifecycle that predecessor
models leave out, and packages the result in a machine-readable, expiring policy
that agents and enforcement layers can consume today.

In plain language: most of these frameworks describe a climb toward a system
capable of acting entirely on its own. LORM describes a climb toward something
else — how much authority has been delegated to the system, and on what evidence
it was earned.

## Sources

Every figure and quotation above was checked against these on 2026-08-04.
Where a standard is paywalled, the citation names the public document that
confirms the wording.

- **SAE J3016** — *Taxonomy and Definitions for Terms Related to Driving
  Automation Systems for On-Road Motor Vehicles*, issued 2014-01, current
  revision J3016_202104 (2021-04-30), superseding JUN2018. Deprecated terms:
  clause 7.1. Publicly previewable as the technically equivalent
  ISO/SAE PAS 22736:2021.
- **TM Forum** — *Autonomous Networks: Empowering Digital Transformation for the
  Telecoms Industry*, Release 1.0, 2019-05-15
  ([PDF](https://www.tmforum.org/wp-content/uploads/2019/05/22553-Autonomous-Networks-whitepaper.pdf));
  *Autonomous Networks Level 4 Industry Blueprint*, 2024-11; IG1252 (levels
  evaluation methodology) and IG1218 (framework), both membership-gated;
  *A Regional Guide to Autonomous Networks Progress*, 2025-06, survey fielded
  February–April 2025, 141 respondents across 91 CSPs
  ([PDF](https://info.tmforum.org/rs/021-WLD-815/images/TM_Forum_-_A_regional_guide_to_autonomous_networks_progress.pdf))
  — the source of every level figure quoted here; *Assessing CSPs' Progress
  Towards Level 4 Autonomous Networks*, 2026-03-18, sample of 125 respondents at
  80 companies per TM Forum's own
  [summary](https://inform.tmforum.org/features-and-opinion/how-telcos-worldwide-are-implementing-an),
  full report gated.
- **IBM** — Paul Horn, *Autonomic Computing: IBM's Perspective on the State of
  Information Technology*, 2001-10; *An Architectural Blueprint for Autonomic
  Computing*, 2005 (source of the MAPE-K name); *Introduction to Autonomic
  Computing*, IBM zSeries Expo, 2004
  ([PDF](https://public.dhe.ibm.com/s390/zos/vse/pdf3/techconf2004/G07.pdf),
  contains the numbered Basic→Autonomic ladder); *IBM Db2 Genius Hub*
  announcement, 2026-05-04.
- **Sheridan & Verplank** — *Human and Computer Control of Undersea
  Teleoperators*, MIT Man-Machine Systems Laboratory, 1978 (DTIC AD-A057655).
- **Parasuraman, Sheridan & Wickens** — *A Model for Types and Levels of Human
  Interaction with Automation*, IEEE Trans. SMC Part A, 30(3):286–297, 2000
  ([DOI](https://doi.org/10.1109/3468.844354)).
- **Feng, McDonald & Zhang** — *Levels of Autonomy for AI Agents*, Knight First
  Amendment Institute, 2025 ([arXiv:2506.12469](https://arxiv.org/abs/2506.12469)).
- **Luo, Li, Fan & Tang** — *Data Agents: Levels, State of the Art, and Open
  Problems*, SIGMOD 2026 tutorial
  ([arXiv:2602.04261](https://arxiv.org/abs/2602.04261)).
- **Hugging Face** — `smolagents` conceptual guide, *Introduction to Agents*
  ([docs](https://huggingface.co/docs/smolagents/conceptual_guides/intro_agents)).
- **NIST ALFUS** — Special Publication 1011-II-1.0, *Autonomy Levels for Unmanned
  Systems Framework, Volume II: Framework Models*, 2007-12; Volume I
  (terminology) 2004 and 2008.
- **Richardson, Fidock & Gunawan** — systematic review of levels-of-autonomy
  taxonomies, *International Journal of Human–Computer Interaction*,
  41(24):15824–15843, 2025
  ([DOI](https://doi.org/10.1080/10447318.2025.2502978)).
- **Postgres.AI** — Samokhvalov, *Self-Driving Postgres*, 2025-07-25
  ([post](https://postgres.ai/blog/20250725-self-driving-postgres)).
- **Oracle** — *What Is an Autonomous AI Database?* product materials; Staimer
  (Dragon Slayer Consulting), Oracle-sponsored white paper containing the only
  0–5 "Database Autonomy Levels" chart hosted on oracle.com.
- **Pavlo et al.** — *Self-Driving Database Management Systems*, CIDR 2017
  ([PDF](https://db.cs.cmu.edu/papers/2017/p42-pavlo-cidr17.pdf)).
