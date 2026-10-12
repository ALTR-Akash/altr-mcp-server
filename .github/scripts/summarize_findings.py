"""Summarize what a weekly check found, as Markdown for the issue it opens.

Usage:
    summarize_findings.py trivy <results.sarif>
    summarize_findings.py newest <pytest.log> <lock-pins.txt> <installed.txt>
"""
import json
import re
import sys
from pathlib import Path

# GitHub caps an issue body at 65536 characters, and one issue can carry
# several summaries; the report script caps the total as well.
MAX_CHARS = 30000
MAX_TESTS = 50
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _read(path):
    """A missing file means that step never ran, which the summary says."""
    try:
        return Path(path).read_text(errors="replace")
    except FileNotFoundError:
        return ""


def _field(text, name):
    match = re.search(rf"^{name}: (.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def trivy(sarif_path):
    text = _read(sarif_path)
    if not text:
        return "The scan did not produce a report. See the run log."
    run = json.loads(text)["runs"][0]
    vulnerabilities, other = {}, 0
    for result in run.get("results", []):
        message = result.get("message", {}).get("text", "")
        package = _field(message, "Package")
        if package:
            installed = _field(message, "Installed Version")
            vulnerabilities[(result["ruleId"], package, installed)] = (
                _field(message, "Severity") or "UNKNOWN", package, installed,
                _field(message, "Fixed Version") or "-", result["ruleId"])
        else:
            # Secret and misconfiguration findings are counted, not described:
            # a public issue naming a secret and its file points straight at it.
            other += 1

    lines = []
    if vulnerabilities:
        lines += ["| Severity | Package | Installed | Fixed in | Advisory |",
                  "|---|---|---|---|---|"]
        rows = sorted(vulnerabilities.values(),
                      key=lambda v: (SEVERITY_ORDER.get(v[0], 9), v[1], v[4]))
        lines += [f"| {sev} | `{pkg}` | {inst} | {fixed} | {rule} |"
                  for sev, pkg, inst, fixed, rule in rows]
    if other:
        lines += ["", f"{other} secret or misconfiguration finding(s). See the run log."]
    return "\n".join(lines) or "The report lists no findings. See the run log."


def _pins(text):
    """Name to versions; uv.lock can pin one package differently per Python."""
    pins = {}
    for line in text.splitlines():
        line = line.split(";")[0].split("#")[0].strip()
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==(\S+)", line)
        if match:
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            pins.setdefault(name, set()).add(match.group(2))
    return pins


def newest(pytest_log, lock_pins, installed):
    log = _read(pytest_log)
    failed = [line[:300] for line in log.splitlines()
              if line.startswith(("FAILED ", "ERROR "))]
    locked, now = _pins(_read(lock_pins)), _pins(_read(installed))
    changed = sorted((name, ", ".join(sorted(locked[name])), version)
                     for name in locked.keys() & now.keys()
                     for version in now[name] - locked[name])
    added = sorted((name, version) for name in now.keys() - locked.keys()
                   for version in now[name])

    lines = ["Failing tests:", ""]
    if failed:
        lines += ["```text", *failed[:MAX_TESTS], "```"]
        if len(failed) > MAX_TESTS:
            lines += [f"...and {len(failed) - MAX_TESTS} more. See the run log."]
    elif log:
        lines += ["None listed. See the run log."]
    else:
        lines += ["The tests did not run, so installing the newest versions likely failed."]
    lines += ["", "Versions that differ from `uv.lock`:", ""]
    if changed or added:
        lines += ["| Package | uv.lock | Installed |", "|---|---|---|"]
        lines += [f"| `{name}` | {old} | {new} |" for name, old, new in changed]
        lines += [f"| `{name}` | - | {new} |" for name, new in added]
    else:
        lines += ["None."]
    return "\n".join(lines)


def main(argv):
    kind, *paths = argv
    summary = {"trivy": trivy, "newest": newest}[kind](*paths)
    if len(summary) > MAX_CHARS:
        cut = summary[:MAX_CHARS]
        summary = cut + ("\n```" if cut.count("```") % 2 else "")
        summary += "\n\n(Truncated. See the run log.)"
    print(summary)


if __name__ == "__main__":
    main(sys.argv[1:])
