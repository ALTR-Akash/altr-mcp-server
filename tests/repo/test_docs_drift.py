"""Guard the documentation against drifting from the live tool registry.

Nothing else in the suite compares prose to code, which is how the 0.4.0
``delete_* -> disconnect_*`` rename shipped green while ``.env.example``
kept advertising names that no longer resolved.

Two classes of drift are covered:

* **Names** — every tool-shaped identifier in the docs must resolve to a
  registered tool.
* **Counts** — every per-domain "(N tools)" heading must match what is
  actually registered. Repo-wide totals are not claimed anywhere and so
  are not checked.

Both derive their expectations from ``register_all``, so a new tool or a
rename fails here until the docs are updated.
"""
import asyncio
import json
import os
import re
from importlib import import_module
from pathlib import Path

import pytest
from fastmcp import FastMCP

from altr_mcp.tools import register_all

# parents[2] walks this file up to the repo root:
# tests/repo/test_docs_drift.py -> tests/repo -> tests -> altr-mcp-server
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"

# One row per tool module: (display name, domain doc, module name).
# Display names must match both the README table and the docs/index.md
# bullet list; the module name must match a file in altr_mcp/tools/.
DOMAINS = (
    ("Databases", "databases.md", "database"),
    ("Tags", "tags.md", "tag"),
    ("Policies & Rules", "policies.md", "policy"),
    ("Classification", "classification.md", "classification"),
    ("Access Management", "access-management.md", "access_management"),
    ("Access Requests", "access-requests.md", "access_request"),
    ("Audits", "audits.md", "audit"),
    ("Audit Reports", "audit-report.md", "audit_report"),
    ("DAM Alerting", "dam-alerting.md", "dam_alerting"),
    ("Telemetry", "telemetry.md", "telemetry"),
    ("Sidecar Configuration", "sidecar-config.md", "sidecar_config"),
    ("Vault Tokenization", "vault-tokenization.md", "vault_tokenization"),
    ("Critical Tokenization", "critical-tokenization.md",
     "critical_tokenization"),
    ("Key Management", "key-management.md", "key_management"),
)

# Files that name tools in prose, config samples, or the LLM instructions.
# CHANGELOG.md is deliberately absent: it documents the historical
# ``delete_* -> disconnect_*`` names on purpose, and those must not resolve.
DOC_SOURCES = (
    "README.md",
    ".env.example",
    "altr_mcp/instructions.md",
)

# A snake_case identifier: two or more lowercase segments.
SNAKE_CASE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")

# API field names that look tool-shaped but are neither tools nor tool
# parameters. list_value is a DAM Alerting filter-tree field.
NOT_TOOLS = frozenset({"list_value"})

# A trailing "(N tools)" on a heading or a list item.
COUNT_SUFFIX = re.compile(r"\((\d+) tools\)")


def _tools_of(register):
    """Register into a throwaway server and return its tool list."""
    mcp = FastMCP("test")
    register(mcp)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(mcp.list_tools())
    finally:
        loop.close()


@pytest.fixture(scope="module")
def registry():
    """Live tool names, parameter names, and per-domain counts."""
    os.environ.setdefault("ORG_ID", "test")
    os.environ.setdefault("MAPI_KEY", "test")
    os.environ.setdefault("MAPI_SECRET", "test")

    tools = _tools_of(register_all)
    names = {t.name for t in tools}
    params = set()
    for tool in tools:
        params |= set((tool.parameters or {}).get("properties", {}) or {})

    counts = {}
    for _, _, module_name in DOMAINS:
        module = import_module(f"altr_mcp.tools.{module_name}")
        counts[module_name] = len(_tools_of(module.register))

    return {
        "names": names,
        "params": params,
        "counts": counts,
        # First segment of every tool name: get_, create_, disconnect_, ...
        # Derived rather than hard-coded so a new verb needs no edit here.
        "prefixes": {n.split("_")[0] for n in names},
    }


def _read(relative_path):
    return (REPO_ROOT / relative_path).read_text()


def _doc_paths():
    return [f"docs/{p.name}" for p in sorted(DOCS_DIR.glob("*.md"))]


def test_domain_table_covers_every_tool_module():
    """DOMAINS lists exactly the modules that register_all imports.

    A new tool module fails here until it is given a domain doc and a row
    in both documentation tables.
    """
    on_disk = {
        p.stem for p in (REPO_ROOT / "altr_mcp" / "tools").glob("*.py")
        if p.stem != "__init__"
    }
    declared = {module_name for _, _, module_name in DOMAINS}
    assert declared == on_disk, (
        f"Modules with no DOMAINS row: {sorted(on_disk - declared)}\n"
        f"DOMAINS rows with no module: {sorted(declared - on_disk)}"
    )


@pytest.mark.parametrize("source", DOC_SOURCES + tuple(_doc_paths()))
def test_documented_tool_names_are_registered(registry, source):
    """Every tool-shaped identifier in the docs resolves to a real tool.

    A token counts as tool-shaped when its first segment is one that some
    registered tool uses (``get_``, ``disconnect_``, ...). Parameter names
    are excluded: ``search_uuid`` is an argument, not a tool, and no
    parameter currently shares a name with a tool.
    """
    unknown = sorted(
        token
        for token in set(SNAKE_CASE.findall(_read(source)))
        if token.split("_")[0] in registry["prefixes"]
        and token not in registry["names"]
        and token not in registry["params"]
        and token not in NOT_TOOLS
    )
    assert not unknown, (
        f"{source} names tools that are not registered: {unknown}\n"
        "Rename them to the current tool names, or add the missing tool."
    )


@pytest.mark.parametrize("display,doc,module_name", DOMAINS)
def test_domain_doc_heading_count(registry, display, doc, module_name):
    """Each domain doc's "(N tools)" heading matches its module."""
    headings = COUNT_SUFFIX.findall(
        "\n".join(
            line for line in _read(f"docs/{doc}").splitlines()
            if line.startswith("#")
        )
    )
    assert headings, f"docs/{doc} heading has no '(N tools)' count"
    assert int(headings[0]) == registry["counts"][module_name], (
        f"docs/{doc} heading says {headings[0]} tools, "
        f"{module_name}.py registers {registry['counts'][module_name]}"
    )


def _parse_index_bullets():
    """Map domain display name -> count from the docs/index.md bullets."""
    found = {}
    pattern = re.compile(r"^- \[([^\]]+)\]\([^)]+\).*\((\d+) tools\)\s*$")
    for line in _read("docs/index.md").splitlines():
        match = pattern.match(line)
        if match:
            found[match.group(1)] = int(match.group(2))
    return found


def _readme_tools_section():
    """The README body between the '## Tools' heading and the next one.

    Scoped deliberately: other README tables (credentials, configuration,
    platform support) must not be mistaken for domain rows.
    """
    lines = _read("README.md").splitlines()
    for start, line in enumerate(lines):
        if line.strip() == "## Tools":
            break
    else:
        raise AssertionError("README.md has no '## Tools' section")
    rest = lines[start + 1:]
    for end, line in enumerate(rest):
        if line.startswith("## "):
            return rest[:end]
    return rest


def _parse_readme_table():
    """Map domain display name -> count from the README domain table."""
    found = {}
    # | [Databases](./docs/databases.md) | 8 | Connect ... |
    pattern = re.compile(r"^\|\s*(?:\[([^\]]+)\]\([^)]+\)|([^|]+?))\s*\|"
                         r"\s*(\d+)\s*\|")
    for line in _readme_tools_section():
        match = pattern.match(line)
        if match:
            name = (match.group(1) or match.group(2)).strip()
            found[name] = int(match.group(3))
    return found


@pytest.mark.parametrize(
    "label,parse", (("docs/index.md", _parse_index_bullets),
                    ("README.md", _parse_readme_table)))
def test_domain_listing_matches_registry(registry, label, parse):
    """Both domain listings cover every domain with the right counts.

    This is what catches a partial table: the README once summed to 93
    under a heading claiming 156, with five domains missing outright.
    """
    listed = parse()
    expected = {
        display: registry["counts"][module_name]
        for display, _, module_name in DOMAINS
    }

    assert set(listed) == set(expected), (
        f"{label} domains missing: {sorted(set(expected) - set(listed))}\n"
        f"{label} domains unexpected: {sorted(set(listed) - set(expected))}"
    )

    wrong = {
        name: (count, expected[name])
        for name, count in listed.items() if count != expected[name]
    }
    assert not wrong, (
        f"{label} counts wrong (listed, actual): {wrong}"
    )


def test_instructions_name_every_domain():
    """altr_mcp/instructions.md must mention every domain.

    This file is sent to the model as server instructions on every session,
    so a domain missing from it is a domain the model is less likely to
    reach for. Four were missing before: Audit Reports, Vault Tokenization,
    Critical Tokenization, and Key Management.

    Only the domain names are checked, not the individual tools. The tool
    list already carries every name and description, so enumerating them
    here would duplicate that and go stale -- which is what happened, with
    58 of 156 tools unlisted.
    """
    text = _read("altr_mcp/instructions.md")

    # Scoped to the listing itself, and the count pinned to len(DOMAINS).
    # A plain whole-file search let the Classification row be deleted while
    # the guard stayed green, because "Classification jobs are async" appears
    # in unrelated guidance near the top.
    heading = f"The {len(DOMAINS)} domains:"
    start = text.find(heading)
    assert start != -1, (
        f"altr_mcp/instructions.md does not introduce the domain list as "
        f"{heading!r} -- the count is stale, or the heading changed"
    )
    end = text.find("Individual tools are not listed here", start)
    assert end != -1, (
        "altr_mcp/instructions.md domain list has no closing paragraph; "
        "this test slices between that heading and it"
    )
    block = text[start:end]

    missing = [display for display, _, _ in DOMAINS if display not in block]
    assert not missing, (
        f"altr_mcp/instructions.md does not name these domains: {missing}"
    )


# Any altr.com host in a URL position: inline links, reference definitions,
# autolinks, bare URLs, and href="". Case-insensitive, userinfo skipped.
#
# The trailing [a-z0-9.-]* captures the whole host rather than stopping at
# altr.com, so docs.altr.com.evil.example is captured in full and fails the
# allow-list instead of matching nothing and slipping through.
DOC_LINK_HOST = re.compile(
    r"(?i)(?:https?:)?//(?:[^/@\s]*@)?([a-z0-9.-]*altr\.com[a-z0-9.-]*)"
)

# docs.altr.com is the public documentation site; the other two are marketing.
# api/altrnet are the documented default API endpoints, which appear as values
# in the README settings table and in .env.example rather than as links.
# Anything else in the altr.com space is internal or per-environment.
ALLOWED_DOC_HOSTS = {
    "docs.altr.com", "www.altr.com", "altr.com",
    "api.live.altr.com", "altrnet.live.altr.com",
}

# Everything that leaves the repo: the PyPI long_description, the wheel
# payload, the Registry listing, and the sample operators copy.
PUBLISHED_SOURCES = (
    "README.md",
    "altr_mcp/instructions.md",
    "server.json",
    ".env.example",
)


@pytest.mark.parametrize(
    "source", PUBLISHED_SOURCES + tuple(_doc_paths()))
def test_no_internal_altr_hosts_are_linked(source):
    """Published docs must not link to a dev or per-org ALTR host.

    The README is rendered on the PyPI project page, so a link to
    docs.dev.altr.com sends readers to an internal environment. Six such
    links were live.
    """
    bad = sorted({
        host.lower() for host in DOC_LINK_HOST.findall(_read(source))
        if host.lower() not in ALLOWED_DOC_HOSTS
    })
    assert not bad, (
        f"{source} links to non-public altr.com hosts: {bad}"
    )


# Anything in scheme position must be a recognized scheme. A positive
# check covers the whole typo class -- hhttps, htps, httpss, ttps -- rather
# than the one literal that happened to ship.
URL_SCHEME = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*)://")
KNOWN_SCHEMES = {"http", "https", "mailto", "file", "git", "ssh"}

# Near-misses that never reach the regex above, because they do not contain
# "://" at all. Single-keystroke slips, as likely as the doubled h.
SCHEME_NEAR_MISSES = ("https;//", "http;//", "https:/w", "http:/w")


@pytest.mark.parametrize(
    "source", PUBLISHED_SOURCES + tuple(_doc_paths()))
def test_no_malformed_url_schemes(source):
    """Catches the `hhttps://` class of typo, which renders as a dead link."""
    text = _read(source)
    bad = sorted({
        scheme for scheme in URL_SCHEME.findall(text)
        if scheme.lower() not in KNOWN_SCHEMES
    })
    assert not bad, f"{source} has malformed URL schemes: {bad}"
    present = [typo for typo in SCHEME_NEAR_MISSES if typo in text.lower()]
    assert not present, f"{source} has malformed URL schemes: {present}"


# The license election lives in three places and they must agree. Before
# they did not: LICENSE.md carried the bare GPL text with no copyright line
# and no election at all, while pyproject declared GPL-3.0-or-later and
# GitHub detected the ambiguous GPL-3.0. GPL-3.0-only and GPL-3.0-or-later
# are different grants, and a notice is the only place the choice is
# recorded -- so the notice must carry the or-later clause, not just any
# GPLv3 wording.
LICENSE_HOLDER = "ALTR Solutions, Inc."
LICENSE_EXPRESSION = "GPL-3.0-or-later"
LICENSE_CLASSIFIER = (
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)"
)


def test_license_election_is_consistent():
    """LICENSE.md, pyproject.toml and the README agree on one grant."""
    license_text = _read("LICENSE.md")
    assert LICENSE_HOLDER in license_text, (
        f"LICENSE.md carries no {LICENSE_HOLDER!r} copyright line, so the "
        "version election is unrecorded"
    )

    # The notice sits above the verbatim license. The GPL's own appendix
    # further down quotes the or-later wording as a template for other
    # programs, so only the notice is checked, not the whole file.
    notice = license_text[:license_text.index("\nGNU General Public License")]
    assert "any later version" in notice, (
        "the LICENSE.md copyright notice does not grant 'any later version', "
        f"so it is GPL-3.0-only rather than {LICENSE_EXPRESSION}"
    )
    assert "version 3 of the License" in notice
    assert f"SPDX-License-Identifier: {LICENSE_EXPRESSION}" in notice, (
        f"LICENSE.md carries no SPDX-License-Identifier: {LICENSE_EXPRESSION}"
    )

    pyproject = _read("pyproject.toml")
    assert f'license = "{LICENSE_EXPRESSION}"' in pyproject, (
        f"pyproject.toml does not declare license = {LICENSE_EXPRESSION!r}"
    )
    assert LICENSE_CLASSIFIER in pyproject, (
        f"pyproject.toml is missing the classifier {LICENSE_CLASSIFIER!r}"
    )

    readme = _read("README.md")
    assert LICENSE_HOLDER in readme
    assert LICENSE_EXPRESSION in readme, (
        f"README does not name {LICENSE_EXPRESSION!r}"
    )


SETTINGS_SECTION_START = "## Configuration"
SETTINGS_SECTION_END = "### Restricting Tools"


def test_readme_documents_every_setting():
    """Every Settings field appears in the README configuration tables.

    settings.py had 20 fields and the README documented 9, so max_retries,
    disable_retry and all seven per-service endpoint overrides were
    undiscoverable without reading the source.

    Field names are checked as their uppercase env-var form, which is how
    pydantic-settings resolves them and how an operator sets them.
    """
    from altr_mcp.settings import Settings

    readme = _read("README.md")
    start = readme.find(SETTINGS_SECTION_START)
    assert start != -1, (
        f"README.md has no {SETTINGS_SECTION_START!r} heading; this test "
        "slices the settings tables from it. Update the constant if the "
        "heading was renamed."
    )
    end = readme.find(SETTINGS_SECTION_END, start)
    assert end != -1, (
        f"README.md has no {SETTINGS_SECTION_END!r} heading after "
        f"{SETTINGS_SECTION_START!r}; the settings tables must sit between "
        "the two."
    )
    section = readme[start:end]

    documented = set(re.findall(r"^\| `([A-Z][A-Z0-9_]*)`", section, re.M))
    expected = {name.upper() for name in Settings.model_fields}

    missing = sorted(expected - documented)
    assert not missing, (
        f"README Configuration section does not document: {missing}"
    )

    unknown = sorted(documented - expected)
    assert not unknown, (
        f"README documents settings that do not exist: {unknown}"
    )


# "## [0.5.5]" -- the newest section is the release being prepared.
CHANGELOG_SECTION = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def test_server_json_matches_newest_changelog_section():
    """server.json tracks the newest release section in the CHANGELOG.

    Between releases that is the last released version, and nobody has to
    touch it: work accumulates under ``## [Unreleased]``, which is not a
    release heading. Renaming that section to a version at release time is
    what makes server.json stale, and this is what then requires the bump.

    These values are what gets published to the MCP Registry -- publish-mcp
    no longer rewrites them from the tag, so a stale one is a wrong registry
    entry rather than a cosmetic detail. It used to be stamped over, which is
    exactly why it went unnoticed release after release.

    Checked against the CHANGELOG rather than the git tags because CI
    checkouts do not fetch tags by default.
    """
    versions = CHANGELOG_SECTION.findall(_read("CHANGELOG.md"))
    assert versions, "CHANGELOG.md has no '## [x.y.z]' section"
    expected = versions[0]

    data = json.loads(_read("server.json"))
    found = {"version": data["version"]}
    for i, package in enumerate(data.get("packages", [])):
        found[f"packages[{i}].version"] = package["version"]

    wrong = {k: v for k, v in found.items() if v != expected}
    assert not wrong, (
        f"server.json {wrong} should be {expected!r}, the newest CHANGELOG "
        "section. See docs/releasing.md step 2."
    )
