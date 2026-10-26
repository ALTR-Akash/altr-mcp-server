"""Unit tests for new transport and restriction settings fields."""
import pytest
from pydantic import ValidationError

from altr_mcp.settings import Settings


def test_mcp_transport_defaults_to_stdio():
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s")
    assert s.mcp_transport == "stdio"


def test_mcp_host_defaults_to_all_interfaces():
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s")
    assert s.mcp_host == "0.0.0.0"


def test_mcp_port_defaults_to_8000():
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s")
    assert s.mcp_port == 8000


def test_restricted_tools_defaults_to_none():
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s")
    assert s.restricted_tools is None


def test_mcp_transport_reads_from_env(monkeypatch):
    monkeypatch.setenv("ORG_ID", "x")
    monkeypatch.setenv("MAPI_KEY", "k")
    monkeypatch.setenv("MAPI_SECRET", "s")
    monkeypatch.setenv("MCP_TRANSPORT", "sse")
    s = Settings()
    assert s.mcp_transport == "sse"


def test_restricted_tools_reads_from_env(monkeypatch):
    monkeypatch.setenv("ORG_ID", "x")
    monkeypatch.setenv("MAPI_KEY", "k")
    monkeypatch.setenv("MAPI_SECRET", "s")
    monkeypatch.setenv("RESTRICTED_TOOLS", "get_tags,disconnect_tag")
    s = Settings()
    assert s.restricted_tools == "get_tags,disconnect_tag"


def test_classification_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.classification_base_url == \
        "https://myorg.classification.live.altr.com"


def test_classification_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_classification_base_url="https://classify.staging.altr.com",
    )
    assert s.classification_base_url == "https://classify.staging.altr.com"


def test_sc_control_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.sc_control_base_url == \
        "https://myorg.sc-control.live.altr.com"


def test_sc_control_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_sc_control_base_url="https://sc.staging.altr.com",
    )
    assert s.sc_control_base_url == "https://sc.staging.altr.com"


def test_service_user_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.service_user_base_url == \
        "https://myorg.service-user.live.altr.com"


def test_service_user_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_service_user_base_url="https://svc.staging.altr.com",
    )
    assert s.service_user_base_url == "https://svc.staging.altr.com"


def test_audit_report_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.audit_report_base_url == \
        "https://myorg.audit-report.live.altr.com/v1"


def test_audit_report_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_audit_report_base_url="https://audit.staging.altr.com/v1",
    )
    assert s.audit_report_base_url == "https://audit.staging.altr.com/v1"


def test_dam_alerting_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.dam_alerting_base_url == \
        "https://myorg.dam-alerting.live.altr.com/v1/dam-alerting"


def test_dam_alerting_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_dam_alerting_base_url="https://dam.staging.altr.com/v1/dam-alerting",
    )
    assert s.dam_alerting_base_url == \
        "https://dam.staging.altr.com/v1/dam-alerting"


def test_vault_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.vault_base_url == \
        "https://myorg.vault.live.altr.com/api/v2"


def test_vault_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_vault_base_url="https://vault.staging.altr.com/api/v2",
    )
    assert s.vault_base_url == "https://vault.staging.altr.com/api/v2"


def test_critical_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.critical_base_url == \
        "https://myorg.critical.live.altr.com/v2"


def test_critical_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_critical_base_url="https://crit.staging.altr.com/v2",
    )
    assert s.critical_base_url == "https://crit.staging.altr.com/v2"


def test_kma_base_url_defaults_to_org_subdomain():
    s = Settings(org_id="myorg", mapi_key="k", mapi_secret="s")
    assert s.kma_base_url == \
        "https://myorg.kma.live.altr.com/v1"


def test_kma_base_url_override():
    s = Settings(
        org_id="myorg",
        mapi_key="k",
        mapi_secret="s",
        altr_kma_base_url="https://kma.staging.altr.com/v1",
    )
    assert s.kma_base_url == "https://kma.staging.altr.com/v1"


def test_retry_and_timeout_defaults():
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s")
    assert s.max_retries == 3
    assert s.request_timeout == 30.0
    assert s.max_retry_after == 60.0


def test_max_retries_of_one_is_allowed():
    """1 means "try once, never retry" -- a valid choice, not an error."""
    s = Settings(org_id="x", mapi_key="k", mapi_secret="s", max_retries=1)
    assert s.max_retries == 1


@pytest.mark.parametrize("field,value", [
    ("max_retries", 0),
    ("max_retries", -1),
    ("request_timeout", 0),
    ("request_timeout", -5),
    ("max_retry_after", -1),
    # 0 reads as "ignore Retry-After" but would clamp every one to zero,
    # turning a 429 into max_retries immediate retries.
    ("max_retry_after", 0),
    # pydantic accepts "inf" as a float. An infinite ceiling silently
    # removes the bound it exists to impose, so the 24-hour park this
    # clamp prevents would be back with no warning.
    ("max_retry_after", float("inf")),
    ("request_timeout", float("inf")),
    ("max_retry_after", float("nan")),
    ("request_timeout", float("nan")),
])
def test_out_of_range_values_are_rejected(field, value):
    """Rejected at startup rather than silently coerced.

    MAX_RETRIES=0 used to reach stop_after_attempt(0) and behave like 1,
    so an operator who meant "no retries" got one attempt and no warning.
    """
    with pytest.raises(ValidationError):
        Settings(org_id="x", mapi_key="k", mapi_secret="s", **{field: value})
