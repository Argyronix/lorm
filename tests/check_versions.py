#!/usr/bin/env python3
"""Fail if the three version lines have drifted apart.

Plugin, specification and policy-schema versions are deliberately
independent, and each is restated in prose in README.md and CLAUDE.md.
Restated numbers rot silently: this ran red against the repository as it
stood on 2026-07-30, where README claimed specification 2.0.0 (SPEC.md said
2.0.2) and policy schema 1.1 (the full example was already at 1.5).

Each version has exactly one source of truth; everything else is a claim
about it, checked here. Stdlib only, so this runs anywhere the engine does.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def find(pattern, text, where):
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        sys.exit(f"check_versions: pattern not found in {where}: {pattern}\n"
                 "The wording moved — update this script with it.")
    return match.group(1)


# --- sources of truth -----------------------------------------------------

manifest = json.loads(read(".claude-plugin/plugin.json"))
plugin = manifest["version"]
spec = find(r"^\*\*Specification, version ([\d.]+)\*\*", read("SPEC.md"),
            "SPEC.md")
# The full example is the newest-features example, so its lorm_policy value
# is the policy schema version the repository currently demonstrates. The
# JSON Schema itself only constrains the shape (^1\.[0-9]+$).
schema = find(r'^lorm_policy:\s*"([\d.]+)"',
              read("schema/examples/full.lorm-policy.yaml"),
              "full.lorm-policy.yaml")

# --- claims about them ----------------------------------------------------

changelog = find(r"^## ([\d.]+) — ", read("CHANGELOG.md"), "CHANGELOG.md")
readme, claude = read("README.md"), read("CLAUDE.md")
readme_status = find(
    r"- Specification ([\d.]+), the agent skill, and the enforcement plugin",
    readme, "README.md status section")
readme_plugin = find(r"enforcement plugin ([\d.]+)\n", readme,
                     "README.md status section")
readme_schema = find(r"policy schema ([\d.]+)\)", readme,
                     "README.md status section")
claude_spec = find(r"semver, currently ([\d.]+)\)", claude, "CLAUDE.md")
claude_plugin = find(r"`plugin\.json`, currently ([\d.]+)\)", claude,
                     "CLAUDE.md")
claude_schema = find(r'`lorm_policy` "1\.0"…"([\d.]+)"', claude, "CLAUDE.md")
citation = read("CITATION.cff")
cff_spec = find(r"^version: ([\d.]+)", citation, "CITATION.cff")
cff_plugin = find(r"at ([\d.]+); the policy schema", citation, "CITATION.cff")
cff_schema = find(r"the policy schema is at ([\d.]+)\.", citation, "CITATION.cff")

CHECKS = [
    ("plugin", plugin, [
        ("CHANGELOG.md latest heading", changelog),
        ("README.md status", readme_plugin),
        ("CLAUDE.md conventions", claude_plugin),
        ("CITATION.cff comment", cff_plugin),
    ]),
    ("specification", spec, [
        ("README.md status", readme_status),
        ("CLAUDE.md conventions", claude_spec),
        ("CITATION.cff version", cff_spec),
    ]),
    ("policy schema", schema, [
        ("README.md status", readme_schema),
        ("CLAUDE.md conventions", claude_schema),
        ("CITATION.cff comment", cff_schema),
    ]),
]

# --- the marketplace entry restates two manifest fields ------------------
# `version` deliberately lives only in plugin.json (it wins over the entry
# anyway, and pinning updates is a release decision, not a listing detail).
# `displayName` and `description` must appear in the entry, because that is
# what a marketplace browser shows before anything is installed — so they are
# duplicated, and therefore checked.

entry = json.loads(read(".claude-plugin/marketplace.json"))["plugins"][0]
if "version" in entry:
    sys.exit("check_versions: marketplace.json restates `version`. Keep it in "
             "plugin.json only — two copies of a version number is the bug "
             "this script exists to catch.")

failures = []
for field in ("displayName", "description"):
    print(f"{field}: {manifest.get(field, '<missing>')!r}")
    ok = entry.get(field) == manifest.get(field)
    print(f"  {'ok  ' if ok else 'DRIFT'} marketplace.json entry")
    if not ok:
        failures.append(f"{field}: marketplace.json says "
                        f"{entry.get(field)!r}, plugin.json says "
                        f"{manifest.get(field)!r}")

for line, truth, claims in CHECKS:
    print(f"{line}: {truth}")
    for where, claimed in claims:
        ok = claimed == truth
        print(f"  {'ok  ' if ok else 'DRIFT'} {where}: {claimed}")
        if not ok:
            failures.append(f"{line}: {where} says {claimed}, truth is {truth}")

if failures:
    print("\nversion drift:", *failures, sep="\n  - ")
    sys.exit(1)
print("\nall version claims agree")
