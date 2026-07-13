# Support

**New to LORM, or something isn't behaving as documented?** Start with
[`docs/user-guide.md`](docs/user-guide.md) — the plain-language intro, six
worked scenarios, and an FAQ cover most first questions (what a level means,
why the hook is silent in your project, why an L5 policy degraded to L4,
how to write a first `lorm-policy.yaml`).

**Found a bug, or want to propose a change?** Open a
[GitHub Issue](https://github.com/Argyronix/lorm/issues/new/choose) — use the
bug report or feature request template. Include your plugin version, policy
schema version, and (for gating bugs) the relevant `.lorm/audit.jsonl` line
or policy snippet — the templates prompt for these.

**Found a security issue** — specifically, anything that lets a gated action
execute without the authorization LORM claims for it (e.g. an L4 action
running without a prompt, or an expired/invalid L5 policy still granting
`allow`) — do not open a public issue. See [`SECURITY.md`](SECURITY.md).

**General questions or discussion** aren't yet routed anywhere separate from
Issues — if that becomes a bottleneck, GitHub Discussions is the natural next
step; for now, open an issue and it'll get relabeled if it isn't a bug or
feature request.

This is a young open-source project maintained on a best-effort basis — there
is no SLA on response time.
