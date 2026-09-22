#!/usr/bin/env python3
"""Fail when shipped code has outrun its version for too long.

Merging a fix before cutting a release is normal — `CONTRIBUTING.md` asks
contributors *not* to bump the version, precisely so the maintainer can batch
changes into one release. What is not normal is forgetting. The 2.7.1→2.7.2 gap
ran six weeks: two contributed fixes sat on `main`, reaching new installs and
nobody else, because an existing install is pinned to the version string in
`plugin.json`. Under one number, different users had different code.

`check_versions.py` could not catch that — it compares numbers with numbers,
and those agreed. This compares the *code* with the last tag, which needs git
history, so it lives apart: `check_versions.py` stays hermetic and cheap enough
to be a required status check, while this one runs on a schedule.

So the condition is not "unreleased changes exist" (that is a working
repository) but "unreleased changes have been waiting longer than a release
cycle should take".

    python3 tests/check_release_drift.py            # default: 14 days
    python3 tests/check_release_drift.py --days 30
    python3 tests/check_release_drift.py --tag v2.7.1   # what-if, for testing

Exit 0 when clean or within the window, 1 when the window is exceeded or the
repository is in a half-released state.
"""

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Paths whose content reaches an installed plugin. tests/ and docs/ are left
# out on purpose: a test or a paragraph changing is not a reason to ask users
# to update, and counting them would make this noisy enough to be ignored.
SHIPPED = [
    "hooks/",
    "skills/",
    "schema/",
    "commands/",
    ".claude-plugin/",
]

DEFAULT_DAYS = 14


def git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"check_release_drift: git {' '.join(args)} failed: "
                 f"{result.stderr.strip()}")
    return result.stdout.strip()


def latest_tag():
    tags = git("tag", "--list", "v*", "--sort=-v:refname").splitlines()
    return tags[0] if tags else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"grace period in days (default {DEFAULT_DAYS})")
    parser.add_argument("--tag", help="compare against this tag instead of the "
                                      "newest one (for testing)")
    args = parser.parse_args()

    tag = args.tag or latest_tag()
    if tag is None:
        print("no v* tag yet — nothing to compare against")
        return 0

    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    declared = manifest["version"]
    tagged = tag.lstrip("v")

    if declared != tagged and not args.tag:
        # plugin.json was bumped but the tag never pushed, or a tag exists for
        # a version the manifest does not claim. Either way the repository is
        # mid-release, and a half-cut release is worth interrupting for.
        print(f"HALF-RELEASED: plugin.json says {declared}, newest tag is "
              f"{tag}.\nEither tag {declared} and publish the release, or "
              f"revert the bump. `git tag v{declared} <commit>` — see CLAUDE.md "
              f"§Releasing.")
        return 1

    log = git("log", f"{tag}..HEAD", "--date=short",
              "--pretty=%h\t%ad\t%an\t%s", "--", *SHIPPED)
    if not log:
        print(f"clean: no shipped-path commits since {tag}")
        return 0

    commits = [line.split("\t", 3) for line in log.splitlines()]
    oldest_date = datetime.date.fromisoformat(commits[-1][1])
    age = (datetime.date.today() - oldest_date).days

    header = (f"{len(commits)} commit(s) touching shipped paths since {tag}, "
              f"oldest {age} day(s) old")
    for sha, date, author, subject in commits:
        header += f"\n  {sha}  {date}  {author}: {subject[:60]}"

    if age <= args.days:
        print(f"within the {args.days}-day window — {header}")
        return 0

    print(f"RELEASE DRIFT: {header}\n\n"
          f"These have been waiting longer than {args.days} days. An install "
          f"is pinned to the version in plugin.json, so until that number "
          f"changes they reach new installs and nobody else. Cut a release "
          f"(CLAUDE.md §Releasing) or say why not.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
