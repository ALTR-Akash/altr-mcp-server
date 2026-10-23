import json

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from altr_mcp.settings import get_settings
from altr_mcp.utils import dam_alerting
from altr_mcp.utils.logging import log_tool


def _parse_filter_tree(value):
    """Accept a dict or a JSON string encoding one; return a dict."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as e:
            raise ValueError(f"filter_tree is not valid JSON: {e}") from e
    if not isinstance(value, dict):
        raise ValueError("filter_tree must be a JSON object")
    return value


def _page_params(limit, contiguous_id) -> dict:
    params = {}
    if limit is not None:
        params["limit"] = limit
    if contiguous_id is not None:
        params["contiguous_id"] = contiguous_id
    return params


def register(mcp: FastMCP) -> None:

    # ── Rules ────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def list_dam_rules(
            limit: int | None = None,
            contiguous_id: str | None = None,
            enabled: bool | None = None,
            severity: str | None = None,
            rule_type: str | None = None
            ) -> dict:
        """List DAM (Data Access Monitoring) alert rules.

        Args:
            limit: Max results per page (default 25, max 100).
            contiguous_id: Pagination token from a prior call. Present in
                the response while has_more is true.
            enabled: Only rules with this enabled flag.
            severity: Only rules of this severity. Values: "low",
                "medium", "high", "critical".
            rule_type: Only rules of this type. Values: "match",
                "threshold".
        """
        settings = get_settings()
        params = _page_params(limit, contiguous_id)
        if enabled is not None:
            params["enabled"] = enabled
        if severity is not None:
            params["severity"] = severity
        if rule_type is not None:
            params["rule_type"] = rule_type
        response = await dam_alerting.list_rules(settings.auth, params)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_dam_rule(rule_id: str) -> dict:
        """Get a single DAM alert rule by ID.

        Args:
            rule_id: ID of the rule.
        """
        settings = get_settings()
        response = await dam_alerting.get_rule(settings.auth, rule_id)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_dam_rule(
            name: str,
            rule_type: str,
            severity: str,
            data_source_scope: str,
            filter_tree: str | dict,
            enabled: bool = True,
            description: str | None = None,
            email_recipients: list[str] | None = None,
            window_type: str | None = None,
            threshold: int | None = None,
            timezone: str | None = None,
            comment_required: bool | None = None,
            email_rate_limit_seconds: int | None = None
            ) -> dict:
        """Create a DAM alert rule that fires alerts on matching audit events.

        A "match" rule fires one alert per matching event. A "threshold"
        rule counts matching events in a tumbling window and fires once per
        window when the count reaches `threshold`.

        rule_type, data_source_scope, filter_tree, window_type, threshold
        and timezone cannot be changed later; to change them, delete the
        rule and create a new one.

        Args:
            name: Display name (max 255 chars).
            rule_type: "match" or "threshold".
            severity: "low", "medium", "high", or "critical".
            data_source_scope: Audit source the rule evaluates. "oltp"
                (sidecar), "snowflake", or "all" (common dimensions only).
            filter_tree: Filter as a dict or JSON string. A node is either
                a junction {"op": "and"|"or", "children": [nodes]} or a
                leaf {"op": ..., "dimension": ..., <value field>}.
                Leaf ops and their value field:
                  eq, neq, contains, regex, cidr → "string_value"
                  in → "list_value" (list of strings)
                  gt, gte, lt, lte → "number_value"
                  range → "range": {"min": n, "max": n}
                  between → "between": {"start": "HH:MM", "end": "HH:MM"}
                    (time_of_day only)
                  key_exists → "string_value" (the key)
                  key_eq → "key_eq": {"key": k, "value": v}
                  exists → no value field
                String ops apply to string dimensions; gt/gte/lt/lte/range
                to numeric ones; key_exists/key_eq to map ones
                (attributes, snowflake_query_tag).
                Common dimensions (any scope): user, database, schema,
                table, column, statement_type, statement_text, event_name,
                time_of_day.
                OLTP only: query_status, repo_user, client_ip, client_app,
                client_port (number), repo_type, repo_host, sidecar_id,
                connection_authorized (bool; exists only),
                authorization_type, oltp_row_count (number),
                bytes_returned (number), policy_applied, policy_type,
                user_email, user_group, execution_role,
                execution_database, execution_schema,
                execution_warehouse, native_statement_type,
                oltp_duration_ms, oltp_rows_inserted, oltp_rows_updated,
                oltp_rows_deleted, oltp_rows_produced, oltp_rows_unloaded
                (numbers), attributes (map).
                Snowflake only: snowflake_role, snowflake_roles,
                snowflake_warehouse, snowflake_warehouse_size,
                snowflake_ip_address, snowflake_client,
                snowflake_session_id, snowflake_query_tag (map),
                snowflake_row_count (number), snowflake_account,
                snowflake_account_region, snowflake_masking_policy,
                snowflake_column_policy, snowflake_execution_duration
                (number), snowflake_tag_name, snowflake_tag_value.
                Example: {"op": "and", "children": [
                  {"op": "eq", "dimension": "database",
                   "string_value": "PROD"},
                  {"op": "in", "dimension": "statement_type",
                   "list_value": ["DELETE", "DROP"]}]}
                Max depth 16, max 256 nodes.
            enabled: Whether the rule is evaluated (default True).
            description: Optional description (max 2000 chars).
            email_recipients: Addresses to email when the rule fires (max
                100). Domains must be allowed for the organization.
            window_type: Threshold rules only (required there).
                "hourly", "daily", "weekly", or "monthly".
            threshold: Threshold rules only (required there). Event count
                (>= 1) that fires the alert.
            timezone: IANA timezone, e.g. "America/New_York". Required on
                threshold rules (aligns windows). On match rules, required
                when filter_tree has a time_of_day leaf and must be
                omitted otherwise.
            comment_required: If True, acknowledging an alert from this
                rule requires a comment.
            email_rate_limit_seconds: Minimum seconds between emails for
                this rule. 0 or omitted uses the platform default (300);
                otherwise 60 to 86400.
        """
        settings = get_settings()
        body: dict = {
            "name": name,
            "rule_type": rule_type,
            "severity": severity,
            "data_source_scope": data_source_scope,
            "filter_tree": _parse_filter_tree(filter_tree),
            "enabled": enabled,
        }
        optional = {
            "description": description,
            "email_recipients": email_recipients,
            "window_type": window_type,
            "threshold": threshold,
            "timezone": timezone,
            "comment_required": comment_required,
            "email_rate_limit_seconds": email_rate_limit_seconds,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        response = await dam_alerting.create_rule(settings.auth, body)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def update_dam_rule(
            rule_id: str,
            name: str | None = None,
            description: str | None = None,
            enabled: bool | None = None,
            severity: str | None = None,
            email_recipients: list[str] | None = None,
            comment_required: bool | None = None,
            email_rate_limit_seconds: int | None = None
            ) -> dict:
        """Update the mutable fields of a DAM alert rule.

        Only the fields passed are changed. rule_type, data_source_scope,
        filter_tree, window_type, threshold and timezone cannot be updated;
        delete the rule and create a new one instead.

        Args:
            rule_id: ID of the rule.
            name: New display name (1-255 chars).
            description: New description (max 2000 chars).
            enabled: Turn evaluation on or off.
            severity: "low", "medium", "high", or "critical".
            email_recipients: Replaces the recipient list. Pass [] to
                remove all recipients.
            comment_required: Require a comment to acknowledge alerts.
            email_rate_limit_seconds: 0 resets to the platform default;
                otherwise 60 to 86400.
        """
        fields = {
            "name": name,
            "description": description,
            "enabled": enabled,
            "severity": severity,
            "email_recipients": email_recipients,
            "comment_required": comment_required,
            "email_rate_limit_seconds": email_rate_limit_seconds,
        }
        body = {k: v for k, v in fields.items() if v is not None}
        if not body:
            raise ValueError("No fields provided to update.")

        settings = get_settings()
        response = await dam_alerting.update_rule(
            settings.auth, rule_id, body)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    @log_tool
    async def delete_dam_rule(rule_id: str) -> dict:
        """Permanently delete a DAM alert rule and stop evaluating it.

        Alerts the rule already fired are kept.

        Args:
            rule_id: ID of the rule.
        """
        settings = get_settings()
        response = await dam_alerting.delete_rule(settings.auth, rule_id)
        return {"success": True, "data": response, "error": None}

    # ── Alerts ───────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def list_dam_alerts(
            limit: int | None = None,
            contiguous_id: str | None = None,
            rule_id: str | None = None,
            state: str | None = None,
            severity: str | None = None
            ) -> dict:
        """List fired DAM alerts, newest first.

        Args:
            limit: Max results per page (default 25, max 100).
            contiguous_id: Pagination token from a prior call. Present in
                the response while has_more is true.
            rule_id: Only alerts fired by this rule.
            state: "new" or "acknowledged".
            severity: "low", "medium", "high", or "critical".
        """
        settings = get_settings()
        params = _page_params(limit, contiguous_id)
        if rule_id is not None:
            params["rule_id"] = rule_id
        if state is not None:
            params["state"] = state
        if severity is not None:
            params["severity"] = severity
        response = await dam_alerting.list_alerts(settings.auth, params)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_dam_alert(alert_id: str) -> dict:
        """Get a single DAM alert by ID.

        Match-rule alerts carry the matched audit event in matched_event;
        threshold alerts carry the count and window in threshold_context.

        Args:
            alert_id: ID of the alert.
        """
        settings = get_settings()
        response = await dam_alerting.get_alert(settings.auth, alert_id)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def acknowledge_dam_alert(
            alert_id: str,
            comment: str | None = None
            ) -> dict:
        """Acknowledge a new DAM alert.

        Fails with 409 if the alert is already acknowledged, and with 400
        if its rule has comment_required set and no comment is given.

        Args:
            alert_id: ID of the alert.
            comment: Acknowledgment comment.
        """
        settings = get_settings()
        body = {"comment": comment} if comment is not None else {}
        response = await dam_alerting.acknowledge_alert(
            settings.auth, alert_id, body)
        return {"success": True, "data": response, "error": None}

    # ── Alert comments ───────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def list_dam_alert_comments(
            alert_id: str,
            limit: int | None = None,
            contiguous_id: str | None = None
            ) -> dict:
        """List investigation comments on a DAM alert, oldest first.

        Args:
            alert_id: ID of the alert.
            limit: Max results per page (default 25, max 100).
            contiguous_id: Pagination token from a prior call.
        """
        settings = get_settings()
        params = _page_params(limit, contiguous_id)
        response = await dam_alerting.list_comments(
            settings.auth, alert_id, params)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_dam_alert_comment(alert_id: str, text: str) -> dict:
        """Add an investigation comment to a DAM alert.

        Comments are append-only; they cannot be edited or deleted.

        Args:
            alert_id: ID of the alert.
            text: Comment text (max 5000 chars).
        """
        settings = get_settings()
        response = await dam_alerting.create_comment(
            settings.auth, alert_id, {"text": text})
        return {"success": True, "data": response, "error": None}
