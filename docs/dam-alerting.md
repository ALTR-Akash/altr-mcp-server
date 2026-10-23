# DAM Alerting Tools (10 tools)

Manage DAM (Data Access Monitoring) alert rules and work the alerts they fire. A rule evaluates sidecar (OLTP) and/or Snowflake audit events against a filter tree. A **match** rule fires one alert per matching event; a **threshold** rule counts matches in a tumbling window and fires once per window when the count reaches its threshold. Alerts can be acknowledged and commented on.

Tools call `https://<ORG_ID>.dam-alerting.live.altr.com/v1/dam-alerting`. Override with `ALTR_DAM_ALERTING_BASE_URL`. API reference: [DAM Alerting API docs](https://docs.dam-alerting.live.altr.com/v1/dam-alerting/docs).

## Tool Summary

| Tool | Description |
|------|-------------|
| `list_dam_rules` | List alert rules |
| `get_dam_rule` | Get a rule by ID |
| `create_dam_rule` | Create a match or threshold rule |
| `update_dam_rule` | Update a rule's mutable fields |
| `delete_dam_rule` | Permanently delete a rule |
| `list_dam_alerts` | List fired alerts, newest first |
| `get_dam_alert` | Get an alert by ID, with its matched event or threshold context |
| `acknowledge_dam_alert` | Acknowledge a new alert |
| `list_dam_alert_comments` | List comments on an alert, oldest first |
| `create_dam_alert_comment` | Add a comment to an alert (append-only) |

## Workflow

1. Create a rule with `create_dam_rule`.
2. Triage with `list_dam_alerts` (filter by `state="new"`, `severity`, or `rule_id`) and `get_dam_alert`.
3. Record findings with `create_dam_alert_comment`.
4. Close out with `acknowledge_dam_alert`. Rules with `comment_required` need a `comment`.

## Pagination

List tools return `items`, `has_more`, and, while more pages remain, `contiguous_id`. Pass that value back as `contiguous_id` for the next page. `limit` defaults to 25, max 100.

## Immutable Fields

`rule_type`, `data_source_scope`, `filter_tree`, `window_type`, `threshold`, and `timezone` are fixed at creation. To change them, delete the rule and create a new one.

## Filter Tree

A node is either a junction or a leaf:

- Junction: `{"op": "and" | "or", "children": [<node>, ...]}`
- Leaf: `{"op": <op>, "dimension": <dimension>, <value field>}`

| Op | Value field | Dimension kind |
|----|-------------|----------------|
| `eq`, `neq`, `contains`, `regex`, `cidr` | `string_value` | string |
| `in` | `list_value` (list of strings) | string |
| `gt`, `gte`, `lt`, `lte` | `number_value` | number |
| `range` | `range: {"min": n, "max": n}` | number |
| `between` | `between: {"start": "HH:MM", "end": "HH:MM"}` | `time_of_day` |
| `key_exists` | `string_value` (the key) | map |
| `key_eq` | `key_eq: {"key": k, "value": v}` | map |
| `exists` | none | any |

Limits: depth 16, 256 nodes, 256 entries per list.

### Dimensions

| Scope | Dimensions |
|-------|------------|
| Any (`oltp`, `snowflake`, `all`) | `user`, `database`, `schema`, `table`, `column`, `statement_type`, `statement_text`, `event_name`, `time_of_day` |
| `oltp` only | `query_status`, `repo_user`, `client_ip`, `client_app`, `client_port`†, `repo_type`, `repo_host`, `sidecar_id`, `connection_authorized`‡, `authorization_type`, `oltp_row_count`†, `bytes_returned`†, `policy_applied`, `policy_type`, `user_email`, `user_group`, `execution_role`, `execution_database`, `execution_schema`, `execution_warehouse`, `native_statement_type`, `oltp_duration_ms`†, `oltp_rows_inserted`†, `oltp_rows_updated`†, `oltp_rows_deleted`†, `oltp_rows_produced`†, `oltp_rows_unloaded`†, `attributes`§ |
| `snowflake` only | `snowflake_role`, `snowflake_roles`, `snowflake_warehouse`, `snowflake_warehouse_size`, `snowflake_ip_address`, `snowflake_client`, `snowflake_session_id`, `snowflake_query_tag`§, `snowflake_row_count`†, `snowflake_account`, `snowflake_account_region`, `snowflake_masking_policy`, `snowflake_column_policy`, `snowflake_execution_duration`†, `snowflake_tag_name`, `snowflake_tag_value` |

† number · ‡ boolean (`exists` only) · § map · all others string

### Timezone

- Threshold rules: `timezone` is required; it aligns the windows.
- Match rules: `timezone` is required when the tree has a `time_of_day` leaf, and must be omitted when it does not.

### Example

Alert on deletes or drops against the `PROD` database through the sidecar during business hours:

```json
{
  "op": "and",
  "children": [
    {"op": "eq", "dimension": "database", "string_value": "PROD"},
    {"op": "in", "dimension": "statement_type", "list_value": ["DELETE", "DROP"]},
    {"op": "between", "dimension": "time_of_day", "between": {"start": "09:00", "end": "17:00"}}
  ]
}
```

with `rule_type="match"`, `data_source_scope="oltp"`, and `timezone="America/New_York"`.

## Tool Details

### list_dam_rules

List alert rules.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | no | Max results per page (default 25, max 100) |
| `contiguous_id` | str | no | Pagination token from a prior call |
| `enabled` | bool | no | Only rules with this enabled flag |
| `severity` | str | no | `"low"`, `"medium"`, `"high"`, or `"critical"` |
| `rule_type` | str | no | `"match"` or `"threshold"` |

---

### get_dam_rule

Get a rule by ID.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rule_id` | str | yes | ID of the rule |

---

### create_dam_rule

Create a match or threshold rule.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | yes | Display name (max 255 chars) |
| `rule_type` | str | yes | `"match"` or `"threshold"` |
| `severity` | str | yes | `"low"`, `"medium"`, `"high"`, or `"critical"` |
| `data_source_scope` | str | yes | `"oltp"`, `"snowflake"`, or `"all"` (common dimensions only) |
| `filter_tree` | dict or str | yes | Filter tree; see [Filter Tree](#filter-tree) |
| `enabled` | bool | no | Evaluate the rule (default `true`) |
| `description` | str | no | Max 2000 chars |
| `email_recipients` | list[str] | no | Addresses to email when the rule fires (max 100). Domains must be allowed for the org |
| `window_type` | str | threshold only | `"hourly"`, `"daily"`, `"weekly"`, or `"monthly"` |
| `threshold` | int | threshold only | Event count (>= 1) that fires the alert |
| `timezone` | str | see [Timezone](#timezone) | IANA name, e.g. `"America/New_York"` |
| `comment_required` | bool | no | Require a comment to acknowledge this rule's alerts |
| `email_rate_limit_seconds` | int | no | Minimum seconds between emails. `0` or unset uses the default (300); otherwise 60–86400 |

---

### update_dam_rule

Update a rule's mutable fields. Only fields passed are changed; at least one is required.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rule_id` | str | yes | ID of the rule |
| `name` | str | no | 1–255 chars |
| `description` | str | no | Max 2000 chars |
| `enabled` | bool | no | Turn evaluation on or off |
| `severity` | str | no | `"low"`, `"medium"`, `"high"`, or `"critical"` |
| `email_recipients` | list[str] | no | Replaces the list; `[]` removes all |
| `comment_required` | bool | no | Require a comment to acknowledge |
| `email_rate_limit_seconds` | int | no | `0` resets to the default; otherwise 60–86400 |

---

### delete_dam_rule

Permanently delete a rule. Alerts it already fired are kept.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rule_id` | str | yes | ID of the rule |

---

### list_dam_alerts

List fired alerts, newest first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | no | Max results per page (default 25, max 100) |
| `contiguous_id` | str | no | Pagination token from a prior call |
| `rule_id` | str | no | Only alerts fired by this rule |
| `state` | str | no | `"new"` or `"acknowledged"` |
| `severity` | str | no | `"low"`, `"medium"`, `"high"`, or `"critical"` |

---

### get_dam_alert

Get an alert by ID. Match-rule alerts carry `matched_event`; threshold alerts carry `threshold_context`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `alert_id` | str | yes | ID of the alert |

---

### acknowledge_dam_alert

Acknowledge a new alert. Returns 409 if already acknowledged, 400 if the rule has `comment_required` and no comment is given.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `alert_id` | str | yes | ID of the alert |
| `comment` | str | no | Acknowledgment comment |

---

### list_dam_alert_comments

List comments on an alert, oldest first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `alert_id` | str | yes | ID of the alert |
| `limit` | int | no | Max results per page (default 25, max 100) |
| `contiguous_id` | str | no | Pagination token from a prior call |

---

### create_dam_alert_comment

Add a comment to an alert. Comments cannot be edited or deleted.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `alert_id` | str | yes | ID of the alert |
| `text` | str | yes | Comment text (max 5000 chars) |
