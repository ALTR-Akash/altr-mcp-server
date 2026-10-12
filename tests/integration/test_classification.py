"""Integration tests for classification tools (altr_mcp/tools/classification.py).

Tests the classification tools using pytest-httpx to mock HTTP responses.
Verifies the {success, data, error} response shape for happy paths.
"""
import json

import httpx
import pytest
from fastmcp import FastMCP
from pytest_httpx import HTTPXMock

from altr_mcp.tools.classification import register
from tests.integration.conftest import get_tool


@pytest.fixture
def mcp():
    _mcp = FastMCP("test")
    register(_mcp)
    return _mcp


# ── get_classifiers ─────────────────────────────────────────────────────


async def test_get_classifiers_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """get_classifiers returns {success, data, error} with classifier list."""
    httpx_mock.add_response(json={
        "classifiers": [
            {
                "classifier_name": "SSN_DETECTOR",
                "description": "Detects SSN patterns",
                "pattern": r"\d{3}-\d{2}-\d{4}",
                "minimum_threshold": 80,
                "sample_size": 100,
                "sample_type": "ROWS",
                "collection_names": ["ALTR Managed"],
                "collection_count": 1,
            }
        ],
        "contiguous_id": None,
    })
    fn = await get_tool(mcp, "get_classifiers")
    result = await fn()
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


# ── create_classifier ───────────────────────────────────────────────────


async def test_create_classifier_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_classifier returns {success, data, error} on successful creation."""
    httpx_mock.add_response(status_code=201, json={
        "classifier": {
            "classifier_name": "MY_CLASSIFIER",
            "description": "Test classifier",
            "compound_ruleset": {"operator": "AND", "conditions": [
                {"target": "ROW_DATA", "pattern": r"\d{3}-\d{2}-\d{4}",
                 "comparator": "matches", "minimum_threshold": 80}]},
            "collection_names": [],
            "collection_count": 0,
        },
    })
    ruleset = {"operator": "AND", "conditions": [{
        "target": "ROW_DATA", "pattern": r"\d{3}-\d{2}-\d{4}",
        "comparator": "matches", "minimum_threshold": 80}]}
    fn = await get_tool(mcp, "create_classifier")
    result = await fn(
        classifier_name="MY_CLASSIFIER",
        description="Test classifier",
        compound_ruleset=ruleset,
    )
    assert result["success"] is True
    assert result["error"] is None
    assert json.loads(httpx_mock.get_requests()[0].content) == {
        "classifier_name": "MY_CLASSIFIER",
        "description": "Test classifier",
        "compound_ruleset": ruleset,
    }


@pytest.mark.parametrize("tool", ["create_classifier", "update_classifier"])
async def test_classifier_tools_offer_only_rulesets(mcp, tool):
    """Pattern-only classifiers are not offered; logic lives in the ruleset."""
    properties = (await mcp.get_tool(tool)).parameters["properties"]
    assert not {"pattern", "minimum_threshold", "sample_size"} & set(properties)
    assert "compound_ruleset" in properties


async def test_create_classifier_requires_a_ruleset(mcp):
    required = (await mcp.get_tool("create_classifier")).parameters["required"]
    assert set(required) == {"classifier_name", "compound_ruleset"}


# ── delete_classifier ───────────────────────────────────────────────────


async def test_delete_classifier_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """delete_classifier returns {success, data, error} on successful deletion."""
    httpx_mock.add_response(status_code=204, content=b"")
    fn = await get_tool(mcp, "delete_classifier")
    result = await fn(classifier_name="MY_CLASSIFIER")
    assert result["success"] is True
    assert result["error"] is None


# ── get_collections ─────────────────────────────────────────────────────


async def test_get_collections_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """get_collections returns {success, data, error} with collection list."""
    httpx_mock.add_response(json={
        "collections": [
            {
                "collection_name": "ALTR Managed",
                "description": "Default collection",
                "classifier_count": 5,
                "org_id": "org-123",
                "deleted_at": None,
            }
        ],
        "contiguous_id": None,
    })
    fn = await get_tool(mcp, "get_collections")
    result = await fn()
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


# ── create_collection ───────────────────────────────────────────────────


async def test_create_collection_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_collection returns {success, data, error} on successful creation."""
    httpx_mock.add_response(status_code=201, json={
        "collection": {
            "collection_name": "MY_COLLECTION",
            "description": "Test collection",
            "classifier_count": 0,
            "org_id": "org-123",
            "deleted_at": None,
        },
    })
    fn = await get_tool(mcp, "create_collection")
    result = await fn(collection_name="MY_COLLECTION", description="Test collection")
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


# ── delete_collection ───────────────────────────────────────────────────


async def test_delete_collection_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """delete_collection returns {success, data, error} on successful deletion."""
    httpx_mock.add_response(status_code=204, content=b"")
    fn = await get_tool(mcp, "delete_collection")
    result = await fn(collection_name="MY_COLLECTION")
    assert result["success"] is True
    assert result["error"] is None


# ── get_jobs ────────────────────────────────────────────────────────────


async def test_get_jobs_happy_path(httpx_mock: HTTPXMock, test_env, mcp):
    """get_jobs returns {success, data, error} with job list."""
    httpx_mock.add_response(json={
        "jobs": [
            {
                "job_id": "j1",
                "database_id": 1,
                "agent_id": "agent-001",
                "collection_name": "ALTR Managed",
                "job_type": "FULL",
                "status": "COMPLETED",
                "classification_type": 1,
                "sample_strategy": "ROWS",
                "started_at": "2025-01-15T10:00:00Z",
                "completed_at": "2025-01-15T10:05:00Z",
                "updated_at": "2025-01-15T10:05:00Z",
                "cols_processed": 50,
                "retry_count": 0,
                "org_id": "org-123",
            }
        ],
        "contiguous_id": None,
    })
    fn = await get_tool(mcp, "get_jobs")
    result = await fn()
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


async def test_get_jobs_with_filters(httpx_mock: HTTPXMock, test_env, mcp):
    """get_jobs passes filter params and returns data."""
    httpx_mock.add_response(json={
        "jobs": [
            {
                "job_id": "j2",
                "database_id": 1,
                "collection_name": "ALTR Managed",
                "job_type": "FULL",
                "status": "RUNNING",
                "classification_type": 1,
                "started_at": "2025-02-01T09:00:00Z",
                "updated_at": "2025-02-01T09:00:00Z",
                "cols_processed": 0,
                "retry_count": 0,
                "org_id": "org-123",
            }
        ],
        "contiguous_id": None,
    })
    fn = await get_tool(mcp, "get_jobs")
    result = await fn(status="RUNNING", limit=5)
    assert result["success"] is True
    assert result["error"] is None


# ── create_job ──────────────────────────────────────────────────────────


async def test_create_job_happy_path(httpx_mock: HTTPXMock, test_env, mcp):
    """create_job returns {success, data, error} on job creation."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "j1",
        "database_id": 1,
        "collection_name": "ALTR Managed",
        "job_type": "FULL",
        "status": "CREATED",
        "classification_type": 0,
        "sample_strategy": "ROWS",
        "started_at": None,
        "completed_at": None,
        "updated_at": "2025-01-15T10:00:00Z",
        "cols_processed": 0,
        "retry_count": 0,
        "org_id": "org-123",
    })
    fn = await get_tool(mcp, "create_job")
    result = await fn(job_type="FULL", database_id=1, collection_name="ALTR Managed")
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result
    request = httpx_mock.get_request()
    assert "/jobs/snowflake" in str(request.url)
    body = json.loads(request.content)
    assert body == {
        "job_type": "FULL",
        "database_id": 1,
        "collection_name": "ALTR Managed",
        "classification_type": "altr_native",
    }


# ── update_job_status ───────────────────────────────────────────────────


async def test_update_job_status_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """update_job_status returns {success, data, error} on successful update."""
    httpx_mock.add_response(json={
        "job_id": "j1",
        "database_id": 1,
        "collection_name": "ALTR Managed",
        "job_type": "FULL",
        "status": "PAUSED",
        "classification_type": 0,
        "updated_at": "2025-01-15T10:02:00Z",
        "cols_processed": 25,
        "retry_count": 0,
        "org_id": "org-123",
    })
    fn = await get_tool(mcp, "update_job_status")
    result = await fn(job_id="j1", status="PAUSED")
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


# ── get_classification_report ───────────────────────────────────────────


async def test_get_classification_report_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """get_classification_report returns {success, data, error} with report data.

    get_job_report makes 2 HTTP calls:
    1. POST to /v1/jobs/{job_id}/report -> returns {"url": "...", "expiration": "..."}
    2. GET <presigned-url> -> returns actual report JSON
    """
    report_url = "https://s3.amazonaws.com/reports/j1"
    # First response: create report -> returns presigned URL + expiration
    httpx_mock.add_response(status_code=201, json={
        "url": report_url,
        "expiration": "2025-01-15T11:00:00Z",
    })
    # Second response: fetch report from presigned URL
    httpx_mock.add_response(json={
        "job_id": "j1",
        "columns": [{"column_name": "EMAIL", "classifier": "EMAIL_DETECTOR"}],
    })
    fn = await get_tool(mcp, "get_classification_report")
    result = await fn(job_id="j1")
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result


async def test_report_download_uses_the_shared_client_and_timeout(
        httpx_mock: HTTPXMock, test_env, mcp, monkeypatch):
    """The presigned GET honors REQUEST_TIMEOUT and shares the client.

    get_job_report fetches the report outside api.request, so it had its own
    one-off httpx.AsyncClient on httpx's 5s default -- short for a report
    download -- and the happy-path test above asserts only the response
    shape, so reverting it was undetectable.
    """
    monkeypatch.setenv("REQUEST_TIMEOUT", "12")
    report_url = "https://s3.amazonaws.com/reports/j1"
    httpx_mock.add_response(status_code=201, json={
        "url": report_url,
        "expiration": "2025-01-15T11:00:00Z",
    })
    httpx_mock.add_response(url=report_url, json={"job_id": "j1"})

    built = 0
    real_init = httpx.AsyncClient.__init__

    def counting_init(self, *args, **kwargs):
        nonlocal built
        built += 1
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", counting_init)

    fn = await get_tool(mcp, "get_classification_report")
    result = await fn(job_id="j1")
    assert result["success"] is True

    # Both the POST and the presigned GET go through one client.
    assert built == 1, f"expected one shared client, {built} were built"
    download = next(
        r for r in httpx_mock.get_requests() if str(r.url) == report_url)
    assert download.extensions["timeout"] == httpx.Timeout(12.0).as_dict()


async def test_report_download_reports_an_expired_url(
        httpx_mock: HTTPXMock, test_env, mcp):
    """An expired presigned URL names the failure instead of crashing.

    S3 answers an expired URL with 403 and an XML body, so the unguarded
    resp.json() raised JSONDecodeError and the operator saw a JSON parse
    error rather than the actual cause.
    """
    report_url = "https://s3.amazonaws.com/reports/j1"
    httpx_mock.add_response(status_code=201, json={
        "url": report_url,
        "expiration": "2025-01-15T11:00:00Z",
    })
    httpx_mock.add_response(
        url=report_url,
        status_code=403,
        text="<Error><Code>AccessDenied</Code></Error>",
    )

    fn = await get_tool(mcp, "get_classification_report")
    result = await fn(job_id="j1")
    inner = result["data"]
    assert inner["success"] is False
    assert inner["status_code"] == 403
    assert "403" in inner["message"]


# ── error path ──────────────────────────────────────────────────────────


async def test_classification_domain_error_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """classification domain returns success:True wrapping an error data payload on 404."""
    httpx_mock.add_response(status_code=404)
    fn = await get_tool(mcp, "delete_classifier")
    # 404 is non-retryable -> api.request returns {success: False} dict
    # Tool wraps it: {success: True, data: {success: False, ...}, error: None}
    result = await fn(classifier_name="NONEXISTENT")
    assert isinstance(result, dict)
    # Tool layer success is True; inner data indicates failure
    assert result["success"] is True
    assert result["error"] is None
    inner = result["data"]
    assert inner.get("success") is False


# ── create_databricks_job ────────────────────────────────────────────────


async def test_create_databricks_job_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_databricks_job returns {success, data, error} on creation."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "dbx-job-uuid-1234",
        "database_id": 42,
        "status": "CREATED",
        "classification_type": 6,
        "platform": "databricks",
    })
    fn = await get_tool(mcp, "create_databricks_job")
    result = await fn(database_id=42)
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result
    request = httpx_mock.get_request()
    assert "/jobs/databricks" in str(request.url)
    body = json.loads(request.content)
    assert body == {"database_id": 42}


async def test_create_databricks_job_with_collection(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_databricks_job forwards collection_name when given."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "dbx-job-uuid-5678",
        "database_id": 57,
        "status": "CREATED",
        "classification_type": 6,
        "platform": "databricks",
    })
    fn = await get_tool(mcp, "create_databricks_job")
    result = await fn(database_id=57, collection_name="financial_pci")
    assert result["success"] is True
    request = httpx_mock.get_request()
    assert "/jobs/databricks" in str(request.url)
    body = json.loads(request.content)
    assert body == {"database_id": 57, "collection_name": "financial_pci"}


# ── create_gdlp_job ──────────────────────────────────────────────────────


async def test_create_gdlp_job_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_gdlp_job (Snowflake GDLP) posts to /v1/jobs/snowflake with a
    gdlp classification_type and wraps the response."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "gdlp-job-uuid-1234",
        "database_id": 42,
        "status": "CREATED",
        "classification_type": 1,
    })
    fn = await get_tool(mcp, "create_gdlp_job")
    result = await fn(database_id=42)
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result
    request = httpx_mock.get_request()
    assert "/jobs/snowflake" in str(request.url)
    body = json.loads(request.content)
    assert body == {"database_id": 42, "classification_type": "gdlp"}


async def test_create_gdlp_job_with_collection_and_sampling(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_gdlp_job forwards collection_name and sampling fields when given."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "gdlp-job-uuid-5678",
        "database_id": 42,
        "status": "CREATED",
        "classification_type": 1,
    })
    fn = await get_tool(mcp, "create_gdlp_job")
    result = await fn(
        database_id=42,
        collection_name="financial_pci",
        sample_size=250,
        sample_type="ROWS",
    )
    assert result["success"] is True
    request = httpx_mock.get_request()
    assert "/jobs/snowflake" in str(request.url)
    body = json.loads(request.content)
    assert body == {
        "database_id": 42,
        "classification_type": "gdlp",
        "collection_name": "financial_pci",
        "sample_size": 250,
        "sample_type": "ROWS",
    }


# ── create_oltp_job ──────────────────────────────────────────────────────


async def test_create_oltp_job_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """create_oltp_job returns {success, data, error} on creation."""
    httpx_mock.add_response(status_code=201, json={
        "job_id": "oltp-job-uuid-1234",
        "repository": {"name": "postgres_db", "type": "Postgres"},
        "collection_name": "oltp-demo",
        "status": "CREATED",
        "classification_type": 5,
    })
    fn = await get_tool(mcp, "create_oltp_job")
    result = await fn(
        agent_id="agent-uuid-1234",
        repo_name="postgres_db",
        service_user_name="postgres_service",
        collection_name="oltp-demo",
    )
    assert result["success"] is True
    assert result["error"] is None
    assert "data" in result
    request = httpx_mock.get_request()
    assert "/jobs/oltp" in str(request.url)
    body = json.loads(request.content)
    # The four required params plus the four defaulted sampling fields.
    assert body == {
        "agent_id": "agent-uuid-1234",
        "repo_name": "postgres_db",
        "service_user_name": "postgres_service",
        "collection_name": "oltp-demo",
        "classification_type": 5,
        "sample_strategy": "ROWS",
        "sample_size": 1000,
        "sample_type": "ROWS",
    }


# ── add/remove classifiers to collection ─────────────────────────────────


async def test_add_classifiers_to_collection_scalar(
        httpx_mock: HTTPXMock, test_env, mcp):
    """A single classifier_names string is wrapped in a one-element list."""
    httpx_mock.add_response(json={"success": True})
    fn = await get_tool(mcp, "add_classifiers_to_collection")
    result = await fn(
        collection_name="my-collection",
        classifier_names="EMAIL",
    )
    assert result["success"] is True
    body = json.loads(httpx_mock.get_request().content)
    assert body == {"classifier_names": ["EMAIL"]}


async def test_add_classifiers_to_collection_list(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"success": True})
    fn = await get_tool(mcp, "add_classifiers_to_collection")
    result = await fn(
        collection_name="my-collection",
        classifier_names=["EMAIL", "SSN"],
    )
    assert result["success"] is True
    body = json.loads(httpx_mock.get_request().content)
    assert body == {"classifier_names": ["EMAIL", "SSN"]}


async def test_remove_classifiers_from_collection_scalar(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(json={"success": True})
    fn = await get_tool(mcp, "remove_classifiers_from_collection")
    result = await fn(
        collection_name="my-collection",
        classifier_names="EMAIL",
    )
    assert result["success"] is True


# ── get_jobs with full filter set ────────────────────────────────────────


async def test_get_jobs_all_filters(httpx_mock: HTTPXMock, test_env, mcp):
    """get_jobs forwards every filter param in the query string."""
    httpx_mock.add_response(json={"jobs": []})
    fn = await get_tool(mcp, "get_jobs")
    result = await fn(
        limit=25,
        contiguous_id="cur",
        status="COMPLETED",
        job_type="FULL",
        database_id=42,
        classification_type=2,
        order="asc",
    )
    assert result["success"] is True
    url = str(httpx_mock.get_request().url)
    for fragment in (
        "limit=25",
        "contiguous_id=cur",
        "status=COMPLETED",
        "job_type=FULL",
        "database_id=42",
        "classification_type=2",
        "order=asc",
    ):
        assert fragment in url


# ── invalid JSON / 5xx retry ─────────────────────────────────────────────────


async def test_classification_invalid_json_response(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(
        content=b"<html>Bad Gateway</html>",
        headers={"Content-Type": "text/html"},
    )
    fn = await get_tool(mcp, "delete_classifier")
    result = await fn(classifier_name="test-classifier")
    assert result["success"] is True
    assert "raw" in result["data"]


async def test_classification_5xx_retry_exhaustion(
        httpx_mock: HTTPXMock, retry_env, mcp):
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(status_code=500)
    fn = await get_tool(mcp, "delete_classifier")
    result = await fn(classifier_name="test-classifier")
    assert result["success"] is True
    assert result["data"]["success"] is False
    assert "Retry exhausted" in result["data"]["message"]


# ══════════════════════════════════════════════════════════════════════════
# Coverage for the remaining classification tools.
#
# Each tool builds a params/data dict from its optional arguments and
# forwards it to altr_mcp.utils.classification. Tests below pass every
# optional argument so the `if x is not None` branches are exercised, not
# just the call itself; a second test covers the bare path where omitting
# the arguments takes a different branch.


# ══════════════════════════════════════════════════════════════════════════


# ── classifiers ─────────────────────────────────────────────────────────


async def test_get_classifier_happy_path(httpx_mock: HTTPXMock, test_env, mcp):
    """get_classifier fetches a single classifier by name."""
    httpx_mock.add_response(json={"classifier_name": "SSN_DETECTOR"})
    fn = await get_tool(mcp, "get_classifier")
    result = await fn(classifier_name="SSN_DETECTOR")
    assert result == {
        "success": True,
        "data": {"classifier_name": "SSN_DETECTOR"},
        "error": None,
    }


async def test_get_classifier_url_encodes_the_name(
        httpx_mock: HTTPXMock, test_env, mcp):
    """A name with a slash is encoded rather than forming a new path segment."""
    httpx_mock.add_response(json={"classifier_name": "a/b"})
    fn = await get_tool(mcp, "get_classifier")
    await fn(classifier_name="a/b")
    assert "a%2Fb" in str(httpx_mock.get_requests()[0].url)


async def test_update_classifier_sends_every_provided_field(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Each optional field provided reaches the request body."""
    httpx_mock.add_response(json={"classifier_name": "C"})
    fn = await get_tool(mcp, "update_classifier")
    result = await fn(
        classifier_name="C",
        description="updated",
        compound_ruleset={"operator": "AND", "conditions": [
            {"target": "METADATA", "comparator": "contains", "pattern": "ssn"}]},
    )
    assert result["success"] is True
    request = httpx_mock.get_requests()[0]
    assert request.method == "PATCH"
    assert json.loads(request.content) == {
        "description": "updated",
        "compound_ruleset": {"operator": "AND", "conditions": [
            {"target": "METADATA", "comparator": "contains", "pattern": "ssn"}]},
        # Only the legacy pattern is cleared; a 0 threshold would match all.
        "pattern": None,
    }


async def test_update_classifier_omits_unset_fields(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Only the name is required; unset fields are left out of the body."""
    httpx_mock.add_response(json={"classifier_name": "C"})
    fn = await get_tool(mcp, "update_classifier")
    result = await fn(classifier_name="C", description="only this")
    assert result["success"] is True
    assert json.loads(httpx_mock.get_requests()[0].content) == {
        "description": "only this"}


# ── collections ─────────────────────────────────────────────────────────


async def test_get_collection_happy_path(httpx_mock: HTTPXMock, test_env, mcp):
    """get_collection fetches a single collection by name."""
    httpx_mock.add_response(json={"collection_name": "ALTR Managed"})
    fn = await get_tool(mcp, "get_collection")
    result = await fn(collection_name="ALTR Managed")
    assert result["success"] is True
    assert result["data"]["collection_name"] == "ALTR Managed"


async def test_update_collection_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """update_collection sends the new description."""
    httpx_mock.add_response(json={"collection_name": "C"})
    fn = await get_tool(mcp, "update_collection")
    result = await fn(collection_name="C", description="new description")
    assert result["success"] is True
    request = httpx_mock.get_requests()[0]
    assert request.method == "PATCH"
    assert json.loads(request.content)["description"] == "new description"


async def test_get_collection_classifiers_with_pagination_args(
        httpx_mock: HTTPXMock, test_env, mcp):
    """limit and contiguous_id are forwarded as query params."""
    httpx_mock.add_response(json={"classifiers": [], "contiguous_id": None})
    fn = await get_tool(mcp, "get_collection_classifiers")
    result = await fn(collection_name="C", limit=25, contiguous_id="abc")
    assert result["success"] is True
    url = str(httpx_mock.get_requests()[0].url)
    assert "limit=25" in url
    assert "contiguous_id=abc" in url


async def test_get_collection_classifiers_without_pagination_args(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Omitting both leaves the query string empty."""
    httpx_mock.add_response(json={"classifiers": []})
    fn = await get_tool(mcp, "get_collection_classifiers")
    result = await fn(collection_name="C")
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


# ── ALTR-managed collection ─────────────────────────────────────────────


async def test_import_altr_managed_classifiers(
        httpx_mock: HTTPXMock, test_env, mcp):
    """import_altr_managed_classifiers POSTs and returns the result."""
    httpx_mock.add_response(json={"imported": 42})
    fn = await get_tool(mcp, "import_altr_managed_classifiers")
    result = await fn()
    assert result["success"] is True
    assert result["data"] == {"imported": 42}
    assert httpx_mock.get_requests()[0].method == "POST"


async def test_get_altr_managed_timestamp(
        httpx_mock: HTTPXMock, test_env, mcp):
    """get_altr_managed_timestamp returns the last-import timestamp."""
    httpx_mock.add_response(json={"timestamp": "2026-08-03T00:00:00Z"})
    fn = await get_tool(mcp, "get_altr_managed_timestamp")
    result = await fn()
    assert result["success"] is True
    assert result["data"]["timestamp"] == "2026-08-03T00:00:00Z"


async def test_list_altr_managed_classifiers_with_pagination_args(
        httpx_mock: HTTPXMock, test_env, mcp):
    """limit and contiguous_id are forwarded."""
    httpx_mock.add_response(json={"classifiers": []})
    fn = await get_tool(mcp, "list_altr_managed_classifiers")
    result = await fn(limit=10, contiguous_id="tok")
    assert result["success"] is True
    url = str(httpx_mock.get_requests()[0].url)
    assert "limit=10" in url and "contiguous_id=tok" in url


async def test_list_altr_managed_classifiers_without_args(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Both arguments are optional."""
    httpx_mock.add_response(json={"classifiers": []})
    fn = await get_tool(mcp, "list_altr_managed_classifiers")
    result = await fn()
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


# ── jobs ────────────────────────────────────────────────────────────────


async def test_get_active_jobs_with_every_filter(
        httpx_mock: HTTPXMock, test_env, mcp):
    """All four optional filters reach the query string."""
    httpx_mock.add_response(json={"jobs": []})
    fn = await get_tool(mcp, "get_active_jobs")
    result = await fn(
        limit=5, contiguous_id="tok", database_id=2167, agent_id="agent-1")
    assert result["success"] is True
    url = str(httpx_mock.get_requests()[0].url)
    for expected in ("limit=5", "contiguous_id=tok",
                     "database_id=2167", "agent_id=agent-1"):
        assert expected in url


async def test_get_active_jobs_without_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Every filter is optional."""
    httpx_mock.add_response(json={"jobs": []})
    fn = await get_tool(mcp, "get_active_jobs")
    result = await fn()
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


async def test_get_job_happy_path(httpx_mock: HTTPXMock, test_env, mcp):
    """get_job fetches one job by id."""
    httpx_mock.add_response(json={"job_id": "j-1", "status": "COMPLETED"})
    fn = await get_tool(mcp, "get_job")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert result["data"]["status"] == "COMPLETED"


async def test_get_job_summary_happy_path(
        httpx_mock: HTTPXMock, test_env, mcp):
    """get_job_summary hits the /summary sub-resource."""
    httpx_mock.add_response(json={"total_columns": 10})
    fn = await get_tool(mcp, "get_job_summary")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert "summary" in str(httpx_mock.get_requests()[0].url)


# ── findings ────────────────────────────────────────────────────────────


async def test_get_job_findings_with_every_filter(
        httpx_mock: HTTPXMock, test_env, mcp):
    """All optional filters are forwarded, including a bool and a list."""
    httpx_mock.add_response(json={"databases": []})
    fn = await get_tool(mcp, "get_job_findings")
    result = await fn(
        job_id="j-1",
        limit=50,
        page_token="pt",
        classifier_name=["SSN", "EMAIL"],
        confirmed_status="pending",
        include_column_status_counts=True,
    )
    assert result["success"] is True
    url = str(httpx_mock.get_requests()[0].url)
    assert "classifier_name=SSN" in url and "classifier_name=EMAIL" in url
    assert "confirmed_status=pending" in url


async def test_get_job_findings_wraps_a_single_classifier_in_a_list(
        httpx_mock: HTTPXMock, test_env, mcp):
    """A bare string classifier_name is normalised to a one-item list."""
    httpx_mock.add_response(json={"databases": []})
    fn = await get_tool(mcp, "get_job_findings")
    result = await fn(job_id="j-1", classifier_name="SSN")
    assert result["success"] is True
    assert httpx_mock.get_requests()[0].url.params.get_list(
        "classifier_name") == ["SSN"]


async def test_get_job_findings_include_counts_false_is_still_sent(
        httpx_mock: HTTPXMock, test_env, mcp):
    """include_column_status_counts=False is a value, not an omission."""
    httpx_mock.add_response(json={"databases": []})
    fn = await get_tool(mcp, "get_job_findings")
    await fn(job_id="j-1", include_column_status_counts=False)
    url = str(httpx_mock.get_requests()[0].url)
    assert "include_column_status_counts=false" in url.lower()


async def test_get_job_findings_without_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    """job_id alone is enough."""
    httpx_mock.add_response(json={"databases": []})
    fn = await get_tool(mcp, "get_job_findings")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


async def test_get_job_findings_schemas(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Drill-down to schemas, with filters."""
    httpx_mock.add_response(json={"schemas": []})
    fn = await get_tool(mcp, "get_job_findings_schemas")
    result = await fn(
        job_id="j-1", database="DB", limit=10, page_token="pt",
        classifier_name="SSN", confirmed_status="approved")
    assert result["success"] is True
    assert "/databases/DB/schemas" in str(httpx_mock.get_requests()[0].url)


async def test_get_job_findings_schemas_minimal(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Only job_id and database are required."""
    httpx_mock.add_response(json={"schemas": []})
    fn = await get_tool(mcp, "get_job_findings_schemas")
    result = await fn(job_id="j-1", database="DB")
    assert result["success"] is True
    url = httpx_mock.get_requests()[0].url
    assert url.path.endswith("/databases/DB/schemas")
    assert not str(url.params)


async def test_get_job_findings_tables(httpx_mock: HTTPXMock, test_env, mcp):
    """Drill-down to tables, with filters."""
    httpx_mock.add_response(json={"tables": []})
    fn = await get_tool(mcp, "get_job_findings_tables")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", limit=10,
        page_token="pt", classifier_name=["SSN"],
        confirmed_status="rejected")
    assert result["success"] is True
    assert "/schemas/SCH/tables" in str(httpx_mock.get_requests()[0].url)


async def test_get_job_findings_tables_minimal(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Filters are optional at the tables level too."""
    httpx_mock.add_response(json={"tables": []})
    fn = await get_tool(mcp, "get_job_findings_tables")
    result = await fn(job_id="j-1", database="DB", schema="SCH")
    assert result["success"] is True
    url = httpx_mock.get_requests()[0].url
    assert url.path.endswith("/schemas/SCH/tables")
    assert not str(url.params)


async def test_get_job_findings_columns(httpx_mock: HTTPXMock, test_env, mcp):
    """Drill-down to columns, with filters."""
    httpx_mock.add_response(json={"columns": []})
    fn = await get_tool(mcp, "get_job_findings_columns")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        limit=10, page_token="pt", classifier_name="SSN",
        confirmed_status="pending")
    assert result["success"] is True
    assert "/tables/TBL/columns" in str(httpx_mock.get_requests()[0].url)


async def test_get_job_findings_columns_minimal(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Filters are optional at the columns level too."""
    httpx_mock.add_response(json={"columns": []})
    fn = await get_tool(mcp, "get_job_findings_columns")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL")
    assert result["success"] is True
    url = httpx_mock.get_requests()[0].url
    assert url.path.endswith("/tables/TBL/columns")
    assert not str(url.params)


async def test_get_job_findings_classifiers(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Drill-down to the classifiers detected on one column."""
    httpx_mock.add_response(json={"classifiers": []})
    fn = await get_tool(mcp, "get_job_findings_classifiers")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        column="COL", limit=10, page_token="pt",
        confirmed_status="approved")
    assert result["success"] is True
    assert "/columns/COL/classifiers" in str(httpx_mock.get_requests()[0].url)


async def test_get_job_findings_classifiers_minimal(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Pagination and status filters are optional."""
    httpx_mock.add_response(json={"classifiers": []})
    fn = await get_tool(mcp, "get_job_findings_classifiers")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        column="COL")
    assert result["success"] is True
    url = httpx_mock.get_requests()[0].url
    assert url.path.endswith("/columns/COL/classifiers")
    assert not str(url.params)


async def test_get_job_findings_lineage(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Lineage takes the full path plus a classifier; all are required."""
    httpx_mock.add_response(json={"conditions": []})
    fn = await get_tool(mcp, "get_job_findings_lineage")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        column="COL", classifier_name="SSN")
    assert result["success"] is True
    assert httpx_mock.get_requests()[0].url.path.endswith(
        "/columns/COL/classifiers/SSN/lineage")


# ── job decisions ───────────────────────────────────────────────────────


async def test_record_job_decision_at_full_scope(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Every scope field provided lands in the POST body."""
    httpx_mock.add_response(json={"recorded": 1})
    fn = await get_tool(mcp, "record_job_decision")
    result = await fn(
        job_id="j-1", confirmed_status="approved", database="DB",
        schema="SCH", table="TBL", column="COL", classifier_name="SSN")
    assert result["success"] is True
    request = httpx_mock.get_requests()[0]
    assert request.method == "POST"
    body = json.loads(request.content)
    assert body == {
        "confirmed_status": "approved",
        "database": "DB",
        "schema": "SCH",
        "table": "TBL",
        "column": "COL",
        "classifier_name": "SSN",
    }


async def test_record_job_decision_job_wide(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Omitting every scope field records a job-wide decision."""
    httpx_mock.add_response(json={"recorded": 99})
    fn = await get_tool(mcp, "record_job_decision")
    result = await fn(job_id="j-1", confirmed_status="rejected")
    assert result["success"] is True
    assert json.loads(httpx_mock.get_requests()[0].content) == {
        "confirmed_status": "rejected"}


async def test_get_job_decisions_with_every_filter(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Scope and pagination filters are forwarded as query params."""
    httpx_mock.add_response(json={"decisions": []})
    fn = await get_tool(mcp, "get_job_decisions")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        column="COL", limit=20, page_token="pt")
    assert result["success"] is True
    url = str(httpx_mock.get_requests()[0].url)
    for expected in ("database=DB", "schema=SCH", "table=TBL",
                     "column=COL", "limit=20", "page_token=pt"):
        assert expected in url


async def test_get_job_decisions_without_filters(
        httpx_mock: HTTPXMock, test_env, mcp):
    """job_id alone returns every decision on the job."""
    httpx_mock.add_response(json={"decisions": []})
    fn = await get_tool(mcp, "get_job_decisions")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


async def test_revoke_job_decisions_at_full_scope(
        httpx_mock: HTTPXMock, test_env, mcp):
    """revoke_job_decisions DELETEs with every scope field as a param."""
    httpx_mock.add_response(json={"revoked": 1})
    fn = await get_tool(mcp, "revoke_job_decisions")
    result = await fn(
        job_id="j-1", database="DB", schema="SCH", table="TBL",
        column="COL", classifier_name="SSN")
    assert result["success"] is True
    request = httpx_mock.get_requests()[0]
    assert request.method == "DELETE"
    url = str(request.url)
    for expected in ("database=DB", "schema=SCH", "table=TBL",
                     "column=COL", "classifier_name=SSN"):
        assert expected in url


async def test_revoke_job_decisions_job_wide(
        httpx_mock: HTTPXMock, test_env, mcp):
    """Omitting every scope field revokes across the whole job."""
    httpx_mock.add_response(json={"revoked": 99})
    fn = await get_tool(mcp, "revoke_job_decisions")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert not str(httpx_mock.get_requests()[0].url.params)


async def test_get_job_review_status(httpx_mock: HTTPXMock, test_env, mcp):
    """get_job_review_status hits the /review-status sub-resource."""
    httpx_mock.add_response(json={
        "total": 10, "approved": 4, "rejected": 1, "pending": 5})
    fn = await get_tool(mcp, "get_job_review_status")
    result = await fn(job_id="j-1")
    assert result["success"] is True
    assert result["data"]["pending"] == 5
    assert "review-status" in str(httpx_mock.get_requests()[0].url)


async def test_report_creation_failure_passes_the_cause_through(
        httpx_mock: HTTPXMock, test_env, mcp):
    """A failed report *creation* keeps its own error shape.

    get_job_report reads ["url"] off the creation response. When creation
    failed -- bad job id, 4xx, retries exhausted -- api.request has already
    returned {success: False, ...} with no "url", so indexing it raised
    KeyError: 'url' and discarded the real cause.
    """
    httpx_mock.add_response(status_code=404, json={"message": "not found"})

    fn = await get_tool(mcp, "get_classification_report")
    result = await fn(job_id="nope")
    inner = result["data"]
    assert inner["success"] is False
    assert inner["status_code"] == 404
    # Only the creation call was made; no download was attempted.
    assert len(httpx_mock.get_requests()) == 1


OLTP_ARGS = {"agent_id": "a", "repo_name": "r", "service_user_name": "s",
             "collection_name": "C"}


async def test_create_oltp_job_sends_no_sampling_for_a_metadata_scan(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(status_code=201, json={"job_id": "j1"})
    fn = await get_tool(mcp, "create_oltp_job")
    await fn(**OLTP_ARGS, sample_strategy="METADATA", sample_size=500)
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["sample_strategy"] == "METADATA"
    assert "sample_size" not in body and "sample_type" not in body


async def test_create_oltp_job_keeps_the_row_default(
        httpx_mock: HTTPXMock, test_env, mcp):
    httpx_mock.add_response(status_code=201, json={"job_id": "j1"})
    fn = await get_tool(mcp, "create_oltp_job")
    await fn(**OLTP_ARGS)
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert (body["sample_size"], body["sample_type"]) == (1000, "ROWS")


async def test_create_oltp_job_needs_a_size_for_percent_sampling(
        httpx_mock: HTTPXMock, test_env, mcp):
    fn = await get_tool(mcp, "create_oltp_job")
    with pytest.raises(Exception, match="required when sample_type is PERCENT"):
        await fn(**OLTP_ARGS, sample_type="PERCENT")
    assert not httpx_mock.get_requests()
