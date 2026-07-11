#!/usr/bin/env python3
"""LORM trust-lifecycle review — analyze the audit log, propose transitions.

Usage:
    python3 lorm_review.py [project_dir] [--json] [--window DAYS]
                           [--min-track N]

Reads the project's lorm-policy.yaml (or .json) and audit log, joins
execution records with their verification records, and reports:

  - PROMOTION candidates (SPEC §6.2): L4 capabilities (or recurring
    human-approved action classes with no policy entry) with a sufficient
    verified track record and zero failures — with a draft L5 policy entry.
  - DEMOTION proposals (SPEC §6.3): capabilities with failed verifications
    not already covered by an active demotion — with a draft demotions[]
    entry.
  - EXPIRY warnings (SPEC §8.2): L5 policies expiring within 14 days, with
    the verification record summary a renewal review needs.
  - HYGIENE findings: verification coverage too low to ever promote,
    stale pending verifications, unknown capabilities in the log.

The analyzer only proposes. It never writes the policy file (SPEC I-8) —
drafts are printed for human review.

Defaults: --window 90 (days of history considered), --min-track 10
(minimum VERIFIED executions for a promotion proposal, SPEC 6-3).
Exit codes: 0 ok (even with findings), 2 usage/environment error.
"""

import datetime
import json
import os
import sys

WINDOW_DAYS = 90
MIN_TRACK = 10
EXPIRY_SOON_DAYS = 14
STALE_PENDING_DAYS = 7
POLICY_CANDIDATES = (
    "lorm-policy.yaml", "lorm-policy.json",
    os.path.join(".lorm", "policy.yaml"), os.path.join(".lorm", "policy.json"),
)


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def load_policy(root):
    for name in POLICY_CANDIDATES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            text = open(path, encoding="utf-8").read()
            if path.endswith(".json"):
                return json.loads(text), path
            try:
                import yaml
            except ImportError:
                fail("policy is YAML but PyYAML is missing (pip install pyyaml)")
            return yaml.safe_load(text), path
    return None, None


def load_audit(policy, root):
    configured = ((policy or {}).get("audit") or {}).get("log") or os.path.join(
        ".lorm", "audit.jsonl")
    path = configured if os.path.isabs(configured) else os.path.join(root, configured)
    if not os.path.isfile(path):
        return [], path
    records = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            records.append({"x-parse-error": f"line {n}"})
    return records, path


def analyze(policy, records, now, window_days, min_track):
    policy = policy or {}
    cutoff = now - datetime.timedelta(days=window_days)
    caps_in_policy = {c.get("id"): c for c in policy.get("capabilities") or []
                      if isinstance(c, dict)}
    active_demotions = {d.get("capability") for d in policy.get("demotions") or []
                        if isinstance(d, dict)}

    parse_errors = [r["x-parse-error"] for r in records if "x-parse-error" in r]
    executions, verifications = {}, {}
    for rec in records:
        if "x-parse-error" in rec:
            continue
        ts = parse_ts(rec.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        cap = rec.get("capability")
        if not cap:
            continue
        if "x-verifies" in rec:
            verifications.setdefault(cap, {})[rec["x-verifies"]] = rec.get("verified")
        elif rec.get("action"):
            executions.setdefault(cap, []).append(rec)

    stats = {}
    for cap, execs in executions.items():
        vmap = verifications.get(cap, {})
        verified = failed = unverifiable = pending = 0
        hourly = {}
        last_failure = None
        for rec in execs:
            status = vmap.get(rec.get("timestamp")) or rec.get("verified", "pending")
            if status == "verified":
                verified += 1
            elif status == "failed":
                failed += 1
                last_failure = max(filter(None, [last_failure,
                                                 rec.get("timestamp")]))
            elif status == "unverifiable":
                unverifiable += 1
            else:
                pending += 1
            hour = (rec.get("timestamp") or "")[:13]
            hourly[hour] = hourly.get(hour, 0) + 1
        levels = {r.get("level") for r in execs}
        stats[cap] = {
            "executions": len(execs),
            "verified": verified, "failed": failed,
            "unverifiable": unverifiable, "pending": pending,
            "peak_hourly": max(hourly.values()) if hourly else 0,
            "levels_seen": sorted(x for x in levels if x),
            "in_policy": cap in caps_in_policy,
            "policy_level": (caps_in_policy.get(cap) or {}).get("level"),
            "demoted": cap in active_demotions,
            "last_failure": last_failure,
        }

    findings = {"promotions": [], "demotions": [], "expiry": [], "hygiene": []}
    today = now.date()

    for cap, s in sorted(stats.items()):
        entry = caps_in_policy.get(cap)
        # --- demotion proposals (SPEC 6-5): failure without active demotion
        if s["failed"] and not s["demoted"]:
            current = s["policy_level"] or "L4"
            to = "L4" if current == "L5" else "L3"
            findings["demotions"].append({
                "capability": cap,
                "reason": (f"{s['failed']} failed verification(s) in the last "
                           f"{window_days}d (last: {s['last_failure']})"),
                "draft": {
                    "capability": cap, "from": current, "to": to,
                    "reason": f"verification failure {s['last_failure']}",
                    "date": today.isoformat(),
                    "until": "re-promotion per SPEC §6.2",
                },
            })
            continue  # a failing capability is never a promotion candidate

        # --- promotion candidates (SPEC 6-2/6-3)
        already_l5 = s["policy_level"] == "L5"
        if already_l5 or s["demoted"]:
            pass
        elif s["verified"] >= min_track and s["failed"] == 0:
            rate = max(1, s["peak_hourly"] * 2)
            draft = {
                "id": cap,
                "level": "L5",
                "policy": {
                    "version": ((entry or {}).get("policy") or {}).get(
                        "version", 0) + 1,
                    "author": "DRAFT — set the human author",
                    "approved_by": "DRAFT — must differ from author (SPEC 8-1)",
                    "approved_at": today.isoformat(),
                    "expires": (today + datetime.timedelta(days=90)).isoformat(),
                    "tested": (f"{s['verified']} verified executions, "
                               f"0 failures, last {window_days}d (this analysis)"),
                },
                "bounds": (entry or {}).get("bounds") or {
                    "targets": ["DRAFT — declare targets"],
                    "blast_radius": {"max_actions_per_hour": rate},
                },
            }
            if entry and entry.get("match"):
                draft["match"] = entry["match"]
            else:
                draft["match"] = {
                    "x-DRAFT": "add command_patterns/path_patterns/"
                               "tool_patterns encoding the target scope"}
            findings["promotions"].append({
                "capability": cap,
                "evidence": (f"{s['verified']} verified executions, 0 failed "
                             f"({s['pending']} pending, "
                             f"{s['unverifiable']} unverifiable); "
                             f"current level: "
                             f"{s['policy_level'] or 'not in policy (L4 via approvals)'}"),
                "note": ("canary scope: keep initial targets/rate narrower "
                         "than the intended final scope (SPEC 6-3)"),
                "draft": draft,
            })
        elif (s["executions"] >= min_track and s["failed"] == 0
              and s["verified"] < min_track):
            findings["hygiene"].append({
                "capability": cap,
                "issue": (f"{s['executions']} executions but only "
                          f"{s['verified']} verified — verification coverage "
                          f"too low to consider promotion (I-7); "
                          f"{s['pending']} records still 'pending'"),
            })

        if not s["in_policy"] and s["executions"] >= 3:
            findings["hygiene"].append({
                "capability": cap,
                "issue": (f"recurring action class ({s['executions']} "
                          f"human-approved executions) with no policy entry — "
                          f"candidate for an explicit L4 entry"),
            })

    # --- expiry warnings (SPEC 8-2)
    for cap, entry in caps_in_policy.items():
        pol = entry.get("policy") if isinstance(entry, dict) else None
        if not isinstance(pol, dict):
            continue
        expires = parse_date(pol.get("expires"))
        if expires is None:
            continue
        days_left = (expires - today).days
        s = stats.get(cap, {})
        if days_left < 0:
            findings["expiry"].append({
                "capability": cap, "expires": expires.isoformat(),
                "status": f"EXPIRED {-days_left}d ago — consumers treat it as "
                          f"L4 (SPEC 13-1); renew or remove the entry",
            })
        elif days_left <= EXPIRY_SOON_DAYS:
            findings["expiry"].append({
                "capability": cap, "expires": expires.isoformat(),
                "status": (f"expires in {days_left}d — renewal review should "
                           f"cover the verification record (SPEC 8-2): "
                           f"{s.get('verified', 0)} verified, "
                           f"{s.get('failed', 0)} failed in {window_days}d"),
            })

    if parse_errors:
        findings["hygiene"].append({
            "capability": "(audit log)",
            "issue": (f"{len(parse_errors)} unparseable line(s) "
                      f"({', '.join(parse_errors[:3])}…) — the enforcement "
                      f"hook degrades L5 to L4 while the log is corrupt"),
        })

    return stats, findings


def yaml_snippet(obj, indent=0):
    """Small dependency-free YAML renderer for draft snippets."""
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                lines.append(yaml_snippet(value, indent + 1))
            else:
                lines.append(f"{pad}{key}: {json.dumps(value, ensure_ascii=False)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                body = yaml_snippet(item, indent + 1).lstrip()
                lines.append(f"{pad}- {body}")
            else:
                lines.append(f"{pad}- {json.dumps(item, ensure_ascii=False)}")
    return "\n".join(lines)


def render_text(stats, findings, window_days):
    out = [f"LORM trust-lifecycle review — last {window_days} days", ""]
    if not stats:
        out.append("No execution records in the window. Nothing to review.")
    else:
        out.append(f"{'capability':38} {'exec':>5} {'ok':>4} {'fail':>4} "
                   f"{'pend':>4}  level")
        for cap, s in sorted(stats.items()):
            level = s["policy_level"] or "-"
            level += " (demoted)" if s["demoted"] else ""
            out.append(f"{cap:38} {s['executions']:>5} {s['verified']:>4} "
                       f"{s['failed']:>4} {s['pending']:>4}  {level}")
    for title, key, render in (
        ("PROMOTION CANDIDATES (SPEC §6.2 — human decision required)",
         "promotions", True),
        ("DEMOTION PROPOSALS (SPEC §6.3)", "demotions", True),
        ("POLICY EXPIRY (SPEC §8.2)", "expiry", False),
        ("HYGIENE", "hygiene", False),
    ):
        items = findings[key]
        if not items:
            continue
        out += ["", f"== {title} =="]
        for item in items:
            out.append(f"- {item['capability']}: "
                       + (item.get("evidence") or item.get("reason")
                          or item.get("status") or item.get("issue", "")))
            if item.get("note"):
                out.append(f"  note: {item['note']}")
            if render and item.get("draft"):
                out.append("  draft (for human review — never self-applied, "
                           "SPEC I-8):")
                out.append(yaml_snippet(item["draft"], indent=2))
    if not any(findings.values()):
        out += ["", "No lifecycle transitions to propose. Steady state."]
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:]]
    as_json, window, min_track = False, WINDOW_DAYS, MIN_TRACK
    root = os.getcwd()
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            as_json = True
        elif arg == "--window":
            i += 1
            window = int(args[i])
        elif arg == "--min-track":
            i += 1
            min_track = int(args[i])
        elif arg.startswith("--"):
            fail(f"unknown option {arg}")
        else:
            root = arg
        i += 1
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        fail(f"not a directory: {root}")

    policy, policy_path = load_policy(root)
    records, audit_path = load_audit(policy, root)
    now = datetime.datetime.now(datetime.timezone.utc)
    stats, findings = analyze(policy, records, now, window, min_track)

    if as_json:
        print(json.dumps({
            "project": root, "policy": policy_path, "audit": audit_path,
            "window_days": window, "min_track": min_track,
            "stats": stats, "findings": findings,
        }, indent=2, ensure_ascii=False))
    else:
        if policy_path is None:
            print("note: no lorm-policy.yaml found — reviewing audit log only\n")
        print(render_text(stats, findings, window))


if __name__ == "__main__":
    main()
