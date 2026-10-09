"""A weekly check that finds a problem opens an issue that says what it found."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCRIPT = REPO_ROOT / ".github" / "scripts" / "report-scheduled-failure.sh"
SUMMARIZE = REPO_ROOT / ".github" / "scripts" / "summarize_findings.py"
SKIPS_SCHEDULE = "github.event_name != 'schedule'"


def _scheduled_workflows():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        if "schedule" in (workflow.get(True) or {}):  # PyYAML reads `on:` as True
            yield pytest.param(workflow, id=path.name)


@pytest.mark.parametrize("workflow", list(_scheduled_workflows()))
def test_every_scheduled_workflow_reports_its_findings(workflow):
    jobs = workflow["jobs"]
    report = jobs["report-failure"]
    needs = report["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    scheduled = {name for name, job in jobs.items()
                 if name != "report-failure" and job.get("if") != SKIPS_SCHEDULE}

    assert set(needs) == scheduled, "every job the schedule runs"
    assert "github.event_name == 'schedule'" in report["if"]
    # A timed-out job ends as cancelled, which failure() does not catch.
    assert "'failure'" in report["if"] and "'cancelled'" in report["if"]
    assert report["permissions"]["issues"] == "write"
    step = next(s for s in report["steps"]
                if str(SCRIPT.relative_to(REPO_ROOT)) in s.get("run", ""))
    assert step["env"]["CHECK_NAME"] and step["env"]["ISSUE_ASSIGNEES"]
    for name in scheduled:  # each check hands its findings to the report
        steps = jobs[name]["steps"]
        uploads = [s for s in steps if "upload-artifact" in s.get("uses", "")
                   and s["with"]["name"].startswith("findings-")]
        assert uploads and all("failure()" in s["if"] for s in uploads), name
        # Without an explicit bash shell, `| tee` hides the test exit code.
        assert all(s.get("shell") == "bash" for s in steps if "| tee" in s.get("run", ""))


@pytest.fixture
def run_script(tmp_path):
    """Run the script against a stand-in `gh` that applies the real --jq filter."""
    if shutil.which("jq") is None:
        pytest.skip("jq is needed to apply the script's filter")
    log, issues = tmp_path / "gh.log", tmp_path / "issues.json"
    fake = tmp_path / "gh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'prev=""; for arg in "$@"; do\n'
        '  [ "$prev" = --jq ] && query=$arg\n'
        f'  [ "$prev" = --body-file ] && cat "$arg" >> "{log}"\n'
        "  prev=$arg\n"
        "done\n"
        'if [ "$1 $2" = "issue list" ]; then '
        f'jq -r "$query" "{issues}"; fi\n'
        'if [ "$1 $2" = "issue create" ]; then '
        'echo https://github.com/owner/repo/issues/9; fi\n'
        'if [ "$1 $2" = "issue edit" ] && [ -n "${REJECT_ASSIGNEE:-}" ]; then exit 1; fi\n')
    fake.chmod(0o755)

    def run(open_issues, findings=None, **env):
        issues.write_text(json.dumps(open_issues))
        findings_dir = tmp_path / "findings"
        if findings is not None:
            (findings_dir / "findings-x").mkdir(parents=True, exist_ok=True)
            (findings_dir / "findings-x" / "findings.md").write_text(findings)
        env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
               "GITHUB_SERVER_URL": "https://github.com",
               "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "42",
               "CHECK_NAME": "Weekly security scan",
               "FINDINGS_DIR": str(findings_dir),
               "ISSUE_ASSIGNEES": "alice,bob", **env}
        result = subprocess.run([str(SCRIPT)], env=env, check=True,  # as the workflow runs it
                                capture_output=True, text=True)
        return log.read_text() + result.stdout
    return run


BOT = {"login": "app/github-actions"}


def test_a_finding_opens_an_assigned_issue_that_lists_it(run_script):
    log = run_script([], findings="| CRITICAL | `anyio` | 4.13.0 | 4.14.2 |")
    create = next(line for line in log.splitlines()
                  if line.startswith("issue create"))

    assert "--title Weekly security scan found a problem " in create
    assert ("issue edit https://github.com/owner/repo/issues/9 --repo owner/repo "
            "--add-assignee alice,bob") in log
    assert "https://github.com/owner/repo/actions/runs/42" in log
    assert "| CRITICAL | `anyio` | 4.13.0 | 4.14.2 |" in log


def test_a_repeat_finding_comments_on_the_open_issue(run_script):
    log = run_script([{"number": 7, "title": "Weekly security scan found a problem",
                       "author": BOT}], findings="new finding")

    assert "issue comment 7 " in log and "new finding" in log
    assert "issue create" not in log


def test_a_near_miss_title_is_not_reused(run_script):
    log = run_script([{"number": 3, "title": "Weekly security scan found a problem!",
                       "author": BOT}])

    assert "issue create" in log


def test_a_same_titled_issue_from_someone_else_is_not_reused(run_script):
    log = run_script([{"number": 5, "title": "Weekly security scan found a problem",
                       "author": {"login": "someone"}}])

    assert "issue create" in log and "issue comment" not in log


def test_a_check_that_never_finished_still_opens_an_issue(run_script):
    log = run_script([])

    assert "No findings were recorded" in log


def test_an_unassignable_maintainer_leaves_one_unassigned_issue(run_script):
    log = run_script([], findings="x", REJECT_ASSIGNEE="1")

    assert sum(line.startswith("issue create") for line in log.splitlines()) == 1
    assert "::warning::Could not assign alice,bob" in log


def test_an_oversized_body_is_cut_to_what_github_accepts(run_script):
    log = run_script([], findings="x" * 200_000)
    body = log.split("issue create", 1)[1]

    assert len(body) < 65536 and "(Truncated. See the run.)" in body


def _summarize(*args):
    return subprocess.run([sys.executable, str(SUMMARIZE), *map(str, args)],
                          capture_output=True, text=True, check=True).stdout


def _result(rule, text, uri="uv.lock"):
    return {"ruleId": rule, "message": {"text": text},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}}}]}


def test_trivy_findings_are_listed_worst_first(tmp_path):
    sarif = tmp_path / "results.sarif"
    sarif.write_text(json.dumps({"runs": [{"results": [
        _result("CVE-2", "Package: pyjwt\nInstalled Version: 2.13.0\n"
                         "Severity: MEDIUM\nFixed Version: 2.14.0"),
        _result("CVE-1", "Package: anyio\nInstalled Version: 4.13.0\n"
                         "Severity: CRITICAL\nFixed Version: 4.14.2"),
        _result("aws-access-key-id", "Type: secret\nSeverity: CRITICAL\n"
                                     "Match: AKIAEXAMPLEKEY", uri="config.py"),
    ]}]}))
    summary = _summarize("trivy", sarif)

    assert summary.index("CVE-1") < summary.index("CVE-2")
    assert "| CRITICAL | `anyio` | 4.13.0 | 4.14.2 | CVE-1 |" in summary
    # Secret findings are counted, never described.
    assert "1 secret or misconfiguration finding(s)" in summary
    assert "AKIAEXAMPLEKEY" not in summary and "config.py" not in summary


def test_newest_findings_name_the_tests_and_the_changed_versions(tmp_path):
    (tmp_path / "pytest.log").write_text(
        "FAILED tests/unit/test_x.py::test_y - AssertionError\n1 failed\n")
    (tmp_path / "lock.txt").write_text(
        "-e .\nfastmcp==3.4.8\nbackports-tarfile==1.2.0 ; python_full_version < '3.12'\n")
    (tmp_path / "installed.txt").write_text(
        "-e file:///repo\nfastmcp==3.4.9\nbackports.tarfile==1.2.0\nnew-dep==1.0\n")
    files = ("pytest.log", "lock.txt", "installed.txt")
    summary = _summarize("newest", *(tmp_path / f for f in files))

    assert "FAILED tests/unit/test_x.py::test_y" in summary
    assert "| `fastmcp` | 3.4.8 | 3.4.9 |" in summary
    assert "| `new-dep` | - | 1.0 |" in summary
    assert "backports" not in summary  # same version, different spelling


def test_newest_findings_say_when_the_tests_never_ran(tmp_path):
    summary = _summarize("newest", tmp_path / "missing.log",
                         tmp_path / "missing", tmp_path / "missing")

    assert "did not run" in summary


def test_newest_findings_list_a_bounded_number_of_tests(tmp_path):
    (tmp_path / "pytest.log").write_text(
        "".join(f"FAILED tests/t.py::test_{i} - AssertionError\n" for i in range(80)))
    summary = _summarize("newest", tmp_path / "pytest.log",
                         tmp_path / "missing", tmp_path / "missing")

    assert "test_49 " in summary and "test_50 " not in summary
    assert "...and 30 more" in summary
