#!/usr/bin/env python3
"""Validate a lorm-policy.yaml against the LORM policy JSON Schema.

Usage:
    python3 validate_policy.py <policy.yaml> [schema.json]

If the schema path is omitted, the script looks for lorm-policy.schema.json
next to this script, then two directories up (repo layout), then in the
policy file's directory.

Exit codes: 0 valid, 1 invalid, 2 usage/environment error.

Beyond JSON Schema validation, performs LORM semantic checks the schema
cannot express:
  - policy.approved_by must differ from policy.author (SPEC 8-1)
  - warns on expired L5 entries (consumers must treat them as L4, SPEC 13-1)
  - warns when a demotion references an unknown capability id
  - match-block checks (schema 1.1): command_patterns require Bash in tools,
    path_patterns require Write/Edit; warns on L5 entries without match
    (soft-only: the enforcement hook cannot grant allow) and on Bash-matched
    L4/L5 entries whose bounds.targets are not hook-verifiable
"""

import datetime
import json
import sys
from pathlib import Path


def fail_env(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


try:
    import yaml
except ImportError:
    fail_env("pyyaml is required: pip install pyyaml")

try:
    import jsonschema
except ImportError:
    fail_env("jsonschema is required: pip install jsonschema")


def find_schema(policy_path: Path, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            fail_env(f"schema not found: {p}")
        return p
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "lorm-policy.schema.json",
        here.parent.parent.parent / "schema" / "lorm-policy.schema.json",
        policy_path.resolve().parent / "lorm-policy.schema.json",
    ):
        if candidate.is_file():
            return candidate
    fail_env("lorm-policy.schema.json not found; pass its path as the second argument")
    raise AssertionError  # unreachable


def as_date(value) -> datetime.date | None:
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def semantic_checks(doc: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for LORM rules the schema cannot express."""
    errors: list[str] = []
    warnings: list[str] = []
    today = datetime.date.today()
    capabilities = doc.get("capabilities") or []
    known_ids = {c.get("id") for c in capabilities if isinstance(c, dict)}

    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        cid = cap.get("id", "<no id>")
        pol = cap.get("policy")
        if isinstance(pol, dict):
            if pol.get("author") and pol.get("author") == pol.get("approved_by"):
                errors.append(
                    f"capability {cid}: policy.approved_by must differ from "
                    f"policy.author (SPEC 8-1)"
                )
            expires = as_date(pol.get("expires"))
            if expires and expires < today:
                warnings.append(
                    f"capability {cid}: policy expired {expires} — consumers "
                    f"must treat this entry as L4 (SPEC 13-1)"
                )
        if cap.get("level") == "L5" and cap.get("rollback") == "irreversible":
            warnings.append(
                f"capability {cid}: irreversible L5 capability — SPEC I-7 "
                f"says this SHOULD be reconsidered"
            )

        verification = cap.get("verification")
        mech_checks = []
        if isinstance(verification, dict):
            mech = verification.get("mechanical")
            if isinstance(mech, dict):
                mech_checks = mech.get("checks") or []
        if mech_checks:
            window = verification.get("window")
            if window and not str(window).startswith("0"):
                warnings.append(
                    f"capability {cid}: verification.mechanical combined with "
                    f"window '{window}' — mechanical checks run immediately; "
                    f"a windowed outcome cannot be mechanically confirmed by "
                    f"the hook (keep it on the agent-verified path)"
                )
            match_tools = (cap.get("match") or {}).get("tools") or []
            has_exit_code = any(
                isinstance(c, dict) and "exit_code" in c for c in mech_checks
            )
            if has_exit_code and "Bash" not in match_tools:
                warnings.append(
                    f"capability {cid}: exit_code check on a non-Bash-matched "
                    f"capability — the exit code is only recoverable for Bash; "
                    f"this check will leave records pending"
                )

        match = cap.get("match")
        if isinstance(match, dict):
            tools = match.get("tools") or []
            if match.get("command_patterns") and tools and "Bash" not in tools:
                errors.append(
                    f"capability {cid}: match.command_patterns requires "
                    f"'Bash' in match.tools"
                )
            if match.get("path_patterns") and tools and not (
                {"Write", "Edit"} & set(tools)
            ):
                errors.append(
                    f"capability {cid}: match.path_patterns requires 'Write' "
                    f"or 'Edit' in match.tools"
                )
            if match.get("input_patterns") and not match.get("tool_patterns"):
                errors.append(
                    f"capability {cid}: match.input_patterns requires "
                    f"match.tool_patterns (input matching is MCP-only)"
                )
            if (
                cap.get("level") in ("L4", "L5")
                and any(p in ("mcp__*", "*", "mcp__*__*")
                        for p in match.get("tool_patterns") or [])
                and not match.get("input_patterns")
            ):
                warnings.append(
                    f"capability {cid}: {cap.get('level')} entry with a "
                    f"broad tool_pattern and no input_patterns — encode the "
                    f"server/tool and target scope"
                )
            if (
                match.get("command_patterns")
                and cap.get("level") in ("L4", "L5")
                and not any(
                    "/" in t or t.startswith(("./", "*"))
                    for t in (cap.get("bounds") or {}).get("targets", [])
                )
            ):
                warnings.append(
                    f"capability {cid}: Bash-matched {cap.get('level')} entry "
                    f"with non-path bounds.targets — the hook cannot verify "
                    f"targets; ensure command_patterns encode the target scope"
                )
        elif cap.get("level") == "L5":
            warnings.append(
                f"capability {cid}: L5 entry without match block — soft-only "
                f"(the enforcement hook cannot grant allow for it)"
            )

    for dem in doc.get("demotions") or []:
        if isinstance(dem, dict) and dem.get("capability") not in known_ids:
            warnings.append(
                f"demotion references capability "
                f"'{dem.get('capability')}' not listed in capabilities[]"
            )

    return errors, warnings


def main() -> None:
    if len(sys.argv) not in (2, 3):
        fail_env(f"usage: {Path(sys.argv[0]).name} <policy.yaml> [schema.json]")

    policy_path = Path(sys.argv[1])
    if not policy_path.is_file():
        fail_env(f"policy file not found: {policy_path}")

    schema_path = find_schema(policy_path, sys.argv[2] if len(sys.argv) == 3 else None)
    schema = json.loads(schema_path.read_text())

    try:
        doc = yaml.safe_load(policy_path.read_text())
    except yaml.YAMLError as exc:
        print(f"INVALID: {policy_path}: YAML parse error: {exc}")
        sys.exit(1)

    if not isinstance(doc, dict):
        print(f"INVALID: {policy_path}: document is not a mapping")
        sys.exit(1)

    # YAML parses bare dates as datetime.date; the schema expects strings.
    def stringify_dates(node):
        if isinstance(node, dict):
            return {k: stringify_dates(v) for k, v in node.items()}
        if isinstance(node, list):
            return [stringify_dates(v) for v in node]
        if isinstance(node, datetime.date):
            return node.isoformat()
        return node

    normalized = stringify_dates(doc)

    validator = jsonschema.Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(normalized), key=lambda e: list(e.path))
    sem_errors, sem_warnings = semantic_checks(doc)

    for w in sem_warnings:
        print(f"warning: {w}")

    if schema_errors or sem_errors:
        print(f"INVALID: {policy_path}")
        for err in schema_errors:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            print(f"  - at {loc}: {err.message}")
        for err in sem_errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"VALID: {policy_path} (schema: {schema_path.name})")


if __name__ == "__main__":
    main()
