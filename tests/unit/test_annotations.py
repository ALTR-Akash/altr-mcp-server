"""Verify MCP tool annotations match naming convention.

All get_* and list_* tools must have readOnlyHint=True.
All destructive tools (delete_* and disconnect_*) must have destructiveHint=True.
All other tools must have no annotations set.
"""
import asyncio
import os
import pytest
from fastmcp import FastMCP
from altr_mcp.tools import register_all


@pytest.fixture(scope="module")
def annotated_mcp():
    """Create a FastMCP instance with all tools registered."""
    os.environ.setdefault("ORG_ID", "test")
    os.environ.setdefault("MAPI_KEY", "test")
    os.environ.setdefault("MAPI_SECRET", "test")
    mcp = FastMCP("test")
    register_all(mcp)
    return mcp


def _get_component(mcp, tool_name):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(mcp.get_tool(tool_name))
    finally:
        loop.close()


# -- Complete lists derived from naming convention --

GET_LIST_TOOLS = [
    # tag.py
    "get_tags", "get_tag_values",
    "get_tag_details_by_group_id", "get_tag_details",
    # policy.py
    "get_policies", "get_rules", "get_roles",
    # classification.py
    "get_classifiers", "get_classifier",
    "get_collections", "get_collection", "get_collection_classifiers",
    "get_altr_managed_timestamp", "list_altr_managed_classifiers",
    "get_jobs", "get_active_jobs", "get_job", "get_job_summary",
    "get_job_findings", "get_job_findings_schemas", "get_job_findings_tables",
    "get_job_findings_columns", "get_job_findings_classifiers",
    "get_job_findings_lineage",
    "get_job_decisions", "get_job_review_status", "get_job_findings_leaves",
    "get_classification_report",
    # database.py
    "get_databases", "get_database_id", "get_service_users",
    # access_request.py
    "get_access_requests", "get_access_request",
    # telemetry.py
    "get_agent_instances", "get_agent_instance",
    "get_agent_task_telemetry",
    "get_sidecar_instances", "get_sidecar_instance",
    "get_task_telemetry",
    # audit.py
    "get_audit_results",
    "get_query_audit_results",
    "get_system_audit_results",
    # sidecar_config.py
    "list_sc_agents", "get_sc_agent",
    "list_sc_agent_tasks",
    "list_sc_repos", "get_sc_repo",
    "list_sc_repo_users", "get_sc_repo_user",
    "list_sc_service_users", "get_sc_service_user",
    "list_sc_sidecars", "get_sc_sidecar",
    "list_sc_sidecar_listeners",
    "list_sc_sidecar_bindings",
    "list_sc_repo_bindings", "get_sc_sidecar_binding",
    # audit_report.py
    "list_report_definitions", "get_report_definition",
    "list_report_instances", "get_report_instance",
    "get_report_instance_download_url",
    "list_report_comments",
    "get_report_sign_off", "list_report_sign_offs",
    # dam_alerting.py
    "list_dam_rules", "get_dam_rule",
    "list_dam_alerts", "get_dam_alert",
    "list_dam_alert_comments",
    # vault_tokenization.py
    "vault_detokenize", "vault_partial_detokenize",
    # critical_tokenization.py
    "critical_detokenize", "critical_partial_detokenize",
    # key_management.py
    "list_tweaks", "get_tweak",
    "list_keys", "get_key",
]

DESTRUCTIVE_TOOLS = [
    # tag.py
    "disconnect_tag", "disconnect_tag_by_details",
    # policy.py
    "delete_policy", "delete_rule",
    # classification.py
    "delete_classifier", "delete_collection",
    "revoke_job_decisions", "revoke_bulk_job_decision",
    # database.py
    "disconnect_database",
    # telemetry.py
    "disconnect_agent_instance",
    "disconnect_sidecar_instance", "delete_task_telemetry",
    # sidecar_config.py
    "disconnect_sc_agent", "delete_sc_agent_task",
    "disconnect_sc_repo", "disconnect_sc_repo_user",
    "disconnect_sc_service_user",
    "disconnect_sc_sidecar", "disconnect_sc_sidecar_binding",
    # audit_report.py
    "archive_report_definition",
    # dam_alerting.py
    "delete_dam_rule",
    # vault_tokenization.py
    "vault_delete_tokens",
    # critical_tokenization.py
    "critical_delete_tokens",
    # key_management.py
    "deactivate_tweak", "deactivate_key",
]

NO_ANNOTATION_TOOLS = [
    # tag.py
    "update_tag", "connect_tag",
    # policy.py
    "create_policy", "add_rules", "update_rule",
    # classification.py
    "create_classifier", "update_classifier",
    "create_collection", "update_collection",
    "import_altr_managed_classifiers",
    "create_job", "create_databricks_job", "create_gdlp_job",
    "create_oltp_job", "update_job_status",
    "add_classifiers_to_collection",
    "remove_classifiers_from_collection",
    "record_job_decision", "record_bulk_job_decision",
    "confirm_job_report", "cancel_job_report",
    # database.py
    "create_database", "create_databricks_database", "update_database",
    "trigger_database_status_sync",
    # access_management.py
    "create_snowflake_access_policy",
    "update_snowflake_access_policy",
    "create_oltp_access_policy",
    "trigger_access_policy_check",
    # access_request.py
    "create_access_request",
    "approve_access_request",
    "deny_access_request", "cancel_access_request",
    # audit.py
    "search_audits",
    "search_query_audits", "search_system_audits",
    # sidecar_config.py
    "create_sc_agent", "update_sc_agent",
    "create_sc_agent_task", "update_sc_agent_task",
    "create_sc_repo", "update_sc_repo",
    "create_sc_repo_user", "update_sc_repo_user",
    "create_sc_service_user", "update_sc_service_user",
    "create_sc_sidecar", "update_sc_sidecar",
    "register_sc_sidecar_listener",
    "deregister_sc_sidecar_listener",
    "create_sc_sidecar_binding",
    # audit_report.py
    "create_report_definition", "update_report_definition",
    "restore_report_definition", "trigger_report_definition",
    "create_report_comment",
    "pin_report_comment", "unpin_report_comment",
    "create_report_sign_off",
    # dam_alerting.py
    "create_dam_rule", "update_dam_rule",
    "acknowledge_dam_alert", "create_dam_alert_comment",
    # vault_tokenization.py
    "vault_tokenize",
    # critical_tokenization.py
    "critical_tokenize",
    # key_management.py
    "create_tweak", "create_key", "rotate_key",
]


def test_all_registered_tools_are_categorized(annotated_mcp):
    """Every registered tool appears in exactly one annotation list.

    Self-validating against the live registration: a newly added tool that
    is missing from all three lists fails here (as create_gdlp_job and
    create_oltp_job once silently did under the old magic-number check).
    """
    loop = asyncio.new_event_loop()
    try:
        tools = loop.run_until_complete(annotated_mcp.list_tools())
    finally:
        loop.close()
    registered = {t.name for t in tools}
    categorized = (
        set(GET_LIST_TOOLS)
        | set(DESTRUCTIVE_TOOLS)
        | set(NO_ANNOTATION_TOOLS)
    )
    # No tool may appear in more than one list.
    assert (
        len(GET_LIST_TOOLS)
        + len(DESTRUCTIVE_TOOLS)
        + len(NO_ANNOTATION_TOOLS)
    ) == len(categorized), "a tool appears in more than one annotation list"
    assert categorized == registered, (
        f"Uncategorized (registered, in no list): {registered - categorized}\n"
        f"Stale (listed, not registered): {categorized - registered}"
    )


@pytest.mark.parametrize("tool_name", GET_LIST_TOOLS)
def test_get_list_tools_have_read_only_hint(
        annotated_mcp, tool_name):
    component = _get_component(annotated_mcp, tool_name)
    assert component.annotations is not None, (
        f"{tool_name} has no annotations"
    )
    assert component.annotations.readOnlyHint is True, (
        f"{tool_name} missing readOnlyHint"
    )


@pytest.mark.parametrize("tool_name", DESTRUCTIVE_TOOLS)
def test_destructive_tools_have_destructive_hint(
        annotated_mcp, tool_name):
    component = _get_component(annotated_mcp, tool_name)
    assert component.annotations is not None, (
        f"{tool_name} has no annotations"
    )
    assert component.annotations.destructiveHint is True, (
        f"{tool_name} missing destructiveHint"
    )


@pytest.mark.parametrize("tool_name", NO_ANNOTATION_TOOLS)
def test_other_tools_have_no_annotation(
        annotated_mcp, tool_name):
    component = _get_component(annotated_mcp, tool_name)
    assert component.annotations is None, (
        f"{tool_name} should have no annotations"
        f" but has {component.annotations}"
    )
