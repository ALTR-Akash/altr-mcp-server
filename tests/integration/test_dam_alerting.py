"""Integration tests for DAM alerting tools (altr_mcp/tools/dam_alerting.py).

Tests the DAM alerting tools using pytest-httpx to mock HTTP responses.
"""
import json

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pytest_httpx import HTTPXMock

from altr_mcp.tools.dam_alerting import register
from tests.integration.conftest import get_tool

BASE = "https://test-org.dam-alerting.live.altr.com/v1/dam-alerting"
RULE_ID = "0195f3c2-7a1b-7c3d-9e4f-1a2b3c4d5e6f"
ALERT_ID = "0195f3c2-8b2c-7d4e-af50-2b3c4d5e6f70"

FILTER_TREE = {
    "op": "and",
    "children": [
        {"op": "eq", "dimension": "database", "string_value": "PROD"},
        {"op": "in", "dimension": "statement_type",
         "list_value": ["DELETE", "DROP"]},
    ],
}


@pytest.fixture
def mcp():
    _mcp = FastMCP("test")
    register(_mcp)
    return _mcp


def _body(httpx_mock):
    return json.loads(httpx_mock.get_request().content)


# ── list_dam_rules ───────────────────────────────────────────────────────────

async def test_list_dam_rules_no_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        url=f"{BASE}/rules", json={"items": [], "has_more": False})
    fn = await get_tool(mcp, "list_dam_rules")
    result = await fn()
    assert result["success"] is True
    assert result["error"] is None
    assert result["data"]["items"] == []
    request = httpx_mock.get_request()
    assert request.method == "GET"
    assert dict(request.url.params) == {}


async def test_list_dam_rules_with_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"items": [], "has_more": False})
    fn = await get_tool(mcp, "list_dam_rules")
    await fn(limit=10, contiguous_id="tok", enabled=False,
             severity="high", rule_type="threshold")
    params = httpx_mock.get_request().url.params
    assert params["limit"] == "10"
    assert params["contiguous_id"] == "tok"
    assert params["enabled"] == "false"
    assert params["severity"] == "high"
    assert params["rule_type"] == "threshold"


# ── get_dam_rule ─────────────────────────────────────────────────────────────

async def test_get_dam_rule(httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        url=f"{BASE}/rules/{RULE_ID}", json={"rule_id": RULE_ID})
    fn = await get_tool(mcp, "get_dam_rule")
    result = await fn(rule_id=RULE_ID)
    assert result["data"]["rule_id"] == RULE_ID


async def test_get_dam_rule_encodes_path_segment(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={})
    fn = await get_tool(mcp, "get_dam_rule")
    await fn(rule_id="../alerts")
    assert httpx_mock.get_request().url.raw_path == \
        b"/v1/dam-alerting/rules/..%2Falerts"


@pytest.mark.parametrize("tool,suffix", [
    ("get_dam_alert", b""),
    ("acknowledge_dam_alert", b"/acknowledge"),
    ("list_dam_alert_comments", b"/comments"),
    ("create_dam_alert_comment", b"/comments"),
])
async def test_alert_tools_encode_path_segment(
        httpx_mock: HTTPXMock, test_env, mcp, tool, suffix):
    httpx_mock.add_response(json={})
    fn = await get_tool(mcp, tool)
    kwargs = {"text": "x"} if tool == "create_dam_alert_comment" else {}
    await fn(alert_id="../rules/x", **kwargs)
    assert httpx_mock.get_request().url.raw_path.split(b"?")[0] == \
        b"/v1/dam-alerting/alerts/..%2Frules%2Fx" + suffix


async def test_get_dam_rule_not_found(httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(status_code=404)
    fn = await get_tool(mcp, "get_dam_rule")
    result = await fn(rule_id=RULE_ID)
    assert result["success"] is True
    assert result["data"]["success"] is False
    assert result["data"]["status_code"] == 404


# ── create_dam_rule ──────────────────────────────────────────────────────────

async def test_create_dam_rule_match_minimal(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/rules", status_code=201,
        json={"rule_id": RULE_ID})
    fn = await get_tool(mcp, "create_dam_rule")
    result = await fn(
        name="Prod deletes",
        rule_type="match",
        severity="high",
        data_source_scope="oltp",
        filter_tree=FILTER_TREE,
    )
    assert result["data"]["rule_id"] == RULE_ID
    # The API rejects window_type, threshold and timezone on a match rule,
    # so the tool omits unset optionals.
    assert _body(httpx_mock) == {
        "name": "Prod deletes",
        "rule_type": "match",
        "severity": "high",
        "data_source_scope": "oltp",
        "filter_tree": FILTER_TREE,
        "enabled": False,
    }


async def test_create_dam_rule_threshold_full(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(status_code=201, json={"rule_id": RULE_ID})
    fn = await get_tool(mcp, "create_dam_rule")
    await fn(
        name="Bulk reads",
        rule_type="threshold",
        severity="critical",
        data_source_scope="snowflake",
        filter_tree=json.dumps(FILTER_TREE),
        enabled=True,
        description="Too many reads",
        email_recipients=["secops@example.com"],
        window_type="hourly",
        threshold=100,
        timezone="America/New_York",
        comment_required=True,
        email_rate_limit_seconds=600,
    )
    body = _body(httpx_mock)
    assert body["filter_tree"] == FILTER_TREE
    assert body["enabled"] is True
    assert body["email_recipients"] == ["secops@example.com"]
    assert body["window_type"] == "hourly"
    assert body["threshold"] == 100
    assert body["timezone"] == "America/New_York"
    assert body["comment_required"] is True
    assert body["email_rate_limit_seconds"] == 600


@pytest.mark.parametrize("filter_tree", ["{not json", "[1, 2]"])
async def test_create_dam_rule_rejects_bad_filter_tree(
        httpx_mock: HTTPXMock, test_env, mcp, filter_tree):
    fn = await get_tool(mcp, "create_dam_rule")
    with pytest.raises((ToolError, ValueError), match="filter_tree"):
        await fn(
            name="x", rule_type="match", severity="low",
            data_source_scope="oltp", filter_tree=filter_tree)
    assert httpx_mock.get_requests() == []


async def test_create_dam_rule_validation_error_passthrough(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        status_code=400, json={"error": {"message": "invalid filter"}})
    fn = await get_tool(mcp, "create_dam_rule")
    result = await fn(
        name="x", rule_type="match", severity="low",
        data_source_scope="oltp", filter_tree=FILTER_TREE)
    assert result["data"]["success"] is False
    assert result["data"]["status_code"] == 400
    assert "invalid filter" in result["data"]["body"]


# ── update_dam_rule ──────────────────────────────────────────────────────────

async def test_update_dam_rule_sends_only_given_fields(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        method="PATCH", url=f"{BASE}/rules/{RULE_ID}",
        json={"rule_id": RULE_ID, "enabled": False})
    fn = await get_tool(mcp, "update_dam_rule")
    await fn(rule_id=RULE_ID, enabled=False, severity="low")
    assert _body(httpx_mock) == {"enabled": False, "severity": "low"}


async def test_update_dam_rule_empty_recipients_clears_list(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"rule_id": RULE_ID})
    fn = await get_tool(mcp, "update_dam_rule")
    await fn(rule_id=RULE_ID, email_recipients=[])
    assert _body(httpx_mock) == {"email_recipients": []}


async def test_update_dam_rule_requires_a_field(
        httpx_mock: HTTPXMock, test_env, mcp):
    fn = await get_tool(mcp, "update_dam_rule")
    with pytest.raises((ToolError, ValueError), match="No fields"):
        await fn(rule_id=RULE_ID)
    assert httpx_mock.get_requests() == []


# ── delete_dam_rule ──────────────────────────────────────────────────────────

async def test_delete_dam_rule(httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        method="DELETE", url=f"{BASE}/rules/{RULE_ID}", status_code=204)
    fn = await get_tool(mcp, "delete_dam_rule")
    result = await fn(rule_id=RULE_ID)
    assert result["data"]["success"] is True
    assert result["data"]["status_code"] == 204


# ── list_dam_alerts ──────────────────────────────────────────────────────────

async def test_list_dam_alerts_with_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"items": [], "has_more": False})
    fn = await get_tool(mcp, "list_dam_alerts")
    await fn(limit=5, rule_id=RULE_ID, state="new", severity="critical")
    request = httpx_mock.get_request()
    assert request.url.path == "/v1/dam-alerting/alerts"
    assert dict(request.url.params) == {
        "limit": "5", "rule_id": RULE_ID,
        "state": "new", "severity": "critical",
    }


# ── get_dam_alert ────────────────────────────────────────────────────────────

async def test_get_dam_alert(httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        url=f"{BASE}/alerts/{ALERT_ID}",
        json={"alert_id": ALERT_ID, "state": "new"})
    fn = await get_tool(mcp, "get_dam_alert")
    result = await fn(alert_id=ALERT_ID)
    assert result["data"]["state"] == "new"


# ── acknowledge_dam_alert ────────────────────────────────────────────────────

async def test_acknowledge_dam_alert_with_comment(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        method="PATCH", url=f"{BASE}/alerts/{ALERT_ID}/acknowledge",
        json={"alert_id": ALERT_ID, "state": "acknowledged"})
    fn = await get_tool(mcp, "acknowledge_dam_alert")
    result = await fn(alert_id=ALERT_ID, comment="Expected batch job")
    assert result["data"]["state"] == "acknowledged"
    assert _body(httpx_mock) == {"comment": "Expected batch job"}


async def test_acknowledge_dam_alert_without_comment(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"state": "acknowledged"})
    fn = await get_tool(mcp, "acknowledge_dam_alert")
    await fn(alert_id=ALERT_ID)
    assert _body(httpx_mock) == {}


async def test_acknowledge_dam_alert_already_acknowledged(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(status_code=409)
    fn = await get_tool(mcp, "acknowledge_dam_alert")
    result = await fn(alert_id=ALERT_ID)
    assert result["data"]["success"] is False
    assert result["data"]["status_code"] == 409


# ── list_dam_alert_comments / create_dam_alert_comment ───────────────────────

async def test_list_dam_alert_comments(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"items": [], "has_more": False})
    fn = await get_tool(mcp, "list_dam_alert_comments")
    await fn(alert_id=ALERT_ID, limit=50, contiguous_id="tok")
    request = httpx_mock.get_request()
    assert request.method == "GET"
    assert request.url.path == f"/v1/dam-alerting/alerts/{ALERT_ID}/comments"
    assert dict(request.url.params) == {
        "limit": "50", "contiguous_id": "tok"}


async def test_create_dam_alert_comment(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/alerts/{ALERT_ID}/comments",
        status_code=201, json={"comment_id": "c1", "text": "Looking"})
    fn = await get_tool(mcp, "create_dam_alert_comment")
    result = await fn(alert_id=ALERT_ID, text="Looking")
    assert result["data"]["comment_id"] == "c1"
    assert _body(httpx_mock) == {"text": "Looking"}


# ── base URL override ────────────────────────────────────────────────────────

async def test_base_url_override(
        httpx_mock: HTTPXMock, test_env, monkeypatch, mcp):
    monkeypatch.setenv(
        "ALTR_DAM_ALERTING_BASE_URL",
        "https://dam.example.test/v1/dam-alerting")
    httpx_mock.add_response(
        url="https://dam.example.test/v1/dam-alerting/alerts",
        json={"items": []})
    fn = await get_tool(mcp, "list_dam_alerts")
    result = await fn()
    assert result["data"]["items"] == []
