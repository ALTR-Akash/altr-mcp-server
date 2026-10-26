"""Support read-only mode: the tool allow-list, and parse_tool_list().

The allow-list fails closed. Do not derive it from readOnlyHint: the two
sets differ in both directions, and tests/unit/test_support_mode.py pins
each difference. See docs/support-mode.md.
"""


def parse_tool_list(raw: str | None) -> set[str]:
    """Parse a comma-separated tool-name env var.

    The middleware and request_write_unlock both read RESTRICTED_TOOLS
    through this, so they cannot disagree about it.
    """
    return {t.strip() for t in (raw or "").split(",") if t.strip()}


# Unannotated because they POST, but they change no governed state, and
# every audit investigation starts with one.
SEARCH_POST_TOOLS = frozenset({
    "search_audits",
    "search_query_audits",
    "search_system_audits",
})

# Annotated readOnlyHint=True, but excluded from support mode: these
# return real customer values, not configuration. See module docstring.
DISCLOSURE_TOOLS = frozenset({
    "critical_detokenize",
    "critical_partial_detokenize",
    "vault_detokenize",
    "vault_partial_detokenize",
})

# The 77 tools available in support mode, grouped by defining module.
SUPPORT_ALLOWED_TOOLS = frozenset({
    # policy.py
    "get_policies", "get_rules", "get_roles",
    # tag.py
    "get_tags", "get_tag_values", "get_tag_details_by_group_id",
    "get_tag_details",
    # classification.py
    "get_classifiers", "get_classifier", "get_collections",
    "get_collection", "get_collection_classifiers",
    "get_altr_managed_timestamp", "list_altr_managed_classifiers",
    "get_jobs", "get_active_jobs", "get_job", "get_job_summary",
    "get_job_findings", "get_job_findings_schemas",
    "get_job_findings_tables", "get_job_findings_columns",
    "get_job_findings_classifiers", "get_job_findings_lineage",
    "get_job_findings_leaves",
    "get_job_decisions", "get_job_review_status",
    "get_classification_report",
    # database.py
    "get_databases", "get_database_id", "get_service_users",
    # access_request.py
    "get_access_requests", "get_access_request",
    # telemetry.py
    "get_agent_instances", "get_agent_instance",
    "get_agent_task_telemetry", "get_sidecar_instances",
    "get_sidecar_instance", "get_task_telemetry",
    # audit.py
    "search_audits", "get_audit_results", "search_system_audits",
    "get_system_audit_results", "search_query_audits",
    "get_query_audit_results",
    # audit_report.py
    "list_report_definitions", "get_report_definition",
    "list_report_instances", "get_report_instance",
    "get_report_instance_download_url", "list_report_comments",
    "get_report_sign_off", "list_report_sign_offs",
    # dam_alerting.py
    "list_dam_rules", "get_dam_rule", "list_dam_alerts", "get_dam_alert",
    "list_dam_alert_comments",
    # sidecar_config.py
    "list_sc_agents", "get_sc_agent", "list_sc_agent_tasks",
    "list_sc_repos", "get_sc_repo", "list_sc_repo_users",
    "get_sc_repo_user", "list_sc_service_users", "get_sc_service_user",
    "list_sc_sidecars", "get_sc_sidecar", "list_sc_sidecar_listeners",
    "list_sc_sidecar_bindings", "list_sc_repo_bindings",
    "get_sc_sidecar_binding",
    # key_management.py
    "list_tweaks", "get_tweak", "list_keys", "get_key",
})
