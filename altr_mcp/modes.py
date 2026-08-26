"""Support read-only mode: the tool allow-list.

Also holds parse_tool_list(), the single parser for comma-separated
tool-name env vars, shared by the RESTRICTED_TOOLS deny-list in
middleware.py and the unlock refusal in tools/support_mode.py so that the
two cannot disagree about what the operator wrote.

When SUPPORT_MODE is enabled, only the tools named in
SUPPORT_ALLOWED_TOOLS are exposed. Everything else is hidden from
tools/list and rejected on tools/call.

This is an allow-list, not a deny-list, and that is deliberate: a tool
added in a future release is unavailable in support mode until someone
adds it here on purpose. A deny-list would expose it by default.

WHY THIS IS NOT DERIVED FROM readOnlyHint
-----------------------------------------
Most of this list is the set of tools carrying
ToolAnnotations(readOnlyHint=True), but the two sets are not the same
and must not be collapsed. They differ in both directions:

  * DISCLOSURE_TOOLS carry readOnlyHint=True and are still excluded.
    The hint is accurate — detokenization mutates nothing — but these
    tools return real customer values. Support investigations read
    configuration and audit history, never plaintext.

  * SEARCH_POST_TOOLS carry no annotation and are still included. They
    are unannotated because each one POSTs a search request rather than
    issuing a GET. They do not change governed state, and they are the
    entry point for every audit investigation.

Keep this file and tests/unit/test_support_mode.py in step. The tests
assert both divergences explicitly so that neither is "tidied up" into
a plain readOnlyHint check later.
"""


def parse_tool_list(raw: str | None) -> set[str]:
    """Parse a comma-separated tool-name env var. One rule, both readers.

    The middleware enforces RESTRICTED_TOOLS and request_write_unlock
    reports on it. If the two parsed differently, the tool would refuse
    an unlock the middleware would have allowed, or grant one it blocks.
    """
    return {t.strip() for t in (raw or "").split(",") if t.strip()}


# Unannotated because they POST a search request, but they change no
# governed state and support cannot investigate an audit trail without
# them. See module docstring.
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

# The 71 tools available in support mode, grouped by defining module.
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
