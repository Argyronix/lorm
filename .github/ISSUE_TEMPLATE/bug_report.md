---
name: Bug report
about: Something in the spec, skill, hook, or schema behaves incorrectly
title: ""
labels: bug
---

**Affected layer** (check one)
- [ ] SPEC.md (normative spec)
- [ ] skills/lorm (agent skill, soft enforcement)
- [ ] hooks/scripts/lorm_gate.py (PreToolUse/PostToolUse hook, hard enforcement)
- [ ] schema/lorm-policy.schema.json (policy schema/validation)
- [ ] docs/ (documentation)
- [ ] other / not sure

**Versions**
- Plugin version (`.claude-plugin/plugin.json` or `/plugin` output):
- Policy schema version (`lorm_policy:` field in your `lorm-policy.yaml`, if any):
- Claude Code version:

**What happened**
A clear description of the observed behavior.

**What you expected**
What the spec, docs, or a previous version led you to expect instead.

**Steps to reproduce**
1.
2.
3.

**Relevant policy** (if the bug involves gating/authorization)
Paste the minimal `lorm-policy.yaml` snippet that reproduces it (redact anything sensitive).

**Relevant audit record** (if the bug involves hook allow/ask/deny decisions)
Paste the matching line(s) from `.lorm/audit.jsonl` (redact anything sensitive). If the hook made a decision you didn't expect, please include which one it returned (allow / ask / deny) and what you expected instead.

**Anything else**
Logs, screenshots, related issues.
