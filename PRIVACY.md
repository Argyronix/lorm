# Data Handling

The LORM plugin collects nothing, transmits nothing, and contacts no network
service. There is no telemetry, no analytics, no crash reporting, and no
account. Everything it does happens on the machine it runs on, and everything
it writes stays inside the project directory.

This page states that plainly because the plugin registers `PreToolUse` and
`PostToolUse` hooks — it sees the tool calls an agent is about to make, which
is a position of some trust, and the honest response is to be specific about
what happens to what it sees.

## What it reads

- **The policy file** in the project (`lorm-policy.yaml`, `lorm-policy.json`,
  or `.lorm/policy.*`). Written by you; read on every gated call.
- **The tool call being evaluated** — for `Bash`, the command text; for
  `Write`/`Edit`, the file path; for MCP tools, the tool name and its input
  parameters. Held in memory for the duration of one decision.
- **Its own audit log**, to evaluate rate limits.
- **Executable conditions** you wrote in the policy (`conditions[].check`) are
  run as shell commands, and their exit status is used. They run with the same
  privileges as the agent's own commands, which is why the policy file is
  yours to write and review.

## What it writes, and where

Everything lives under `.lorm/` in the project:

| File | Contents |
| --- | --- |
| `audit.jsonl` | One append-only record per gated execution: capability id, level, authorizer, a truncated action summary, and outcome text truncated to 300 characters |
| `observations.jsonl` | State-changing actions no policy entry claimed, recorded as **skeletons** — paths, numbers, flag values and any other argument are replaced with placeholders (`«PATH»`, `«N»`, `«V»`, `«ARG»`) before writing, so payloads are not retained |
| `hook-active` | A marker file with fixed text, so the agent skill knows the hook is running |

Nothing else is written, and nothing is written outside the project.

## What leaves the machine

Nothing. The engine imports only the Python standard library; PyYAML is used
solely to parse a YAML policy file, and a JSON policy needs no third-party
package at all. There is no HTTP client in the code path, and continuous
integration verifies that the enforcement path works in an environment with no
third-party packages installed.

You can confirm all of this by reading one file:
[`hooks/scripts/lorm_gate.py`](hooks/scripts/lorm_gate.py).

## Your data, your files

The audit log is yours. Rotate it by moving it aside; do not edit it in place —
the hook denies truncation of its own log, because an audit trail that can be
quietly rewritten is not one (SPEC I-6). Deleting `.lorm/` removes every trace
the plugin has kept, and costs you only the accumulated trust history.

## Contact

Questions about this page, or anything else: <contact@argyronix.com>.
Security reports go through [`SECURITY.md`](SECURITY.md).
