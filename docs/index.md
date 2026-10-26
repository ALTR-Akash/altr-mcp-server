title: ALTR MCP Server

# ALTR MCP Server Documentation

Tools for managing data security on the ALTR platform.

## Domains

- [Databases](databases.md) — Connect, manage, and monitor database connections (8 tools)
- [Tags](tags.md) — Connect and manage Snowflake tags for masking policies (8 tools)
- [Policies & Rules](policies.md) — Create masking policies and configure per-role masking rules; includes Databricks PUSHDOWN policies and `get_roles` (8 tools)
- [Classification](classification.md) — Run automated data classification scans and manage classifiers; includes Snowflake/Databricks GDLP, on-demand OLTP scans, findings tree navigation, and human review decisions (41 tools)
- [Access Management](access-management.md) — Create and manage Snowflake and OLTP access management policies (4 tools)
- [Access Requests](access-requests.md) — Submit and manage data access approval requests (6 tools)
- [Audits](audits.md) — Search sidecar, Snowflake query, and system audit logs (6 tools)
- [Audit Reports](audit-report.md) — Create, schedule, and review structured audit report definitions and instances (17 tools)
- [DAM Alerting](dam-alerting.md) — Create match and threshold alert rules over audit events; triage, comment on, and acknowledge the alerts they fire (10 tools)
- [Telemetry](telemetry.md) — Monitor agent and sidecar instance health (9 tools)
- [Sidecar Configuration](sidecar-config.md) — Manage agents, repos, sidecars, listeners, bindings, and tasks (37 tools)
- [Vault Tokenization](vault-tokenization.md) — Tokenize and detokenize values using ALTR vaulted tokenization (4 tools)
- [Critical Tokenization](critical-tokenization.md) — Tokenize and detokenize values using ALTR critical tokenization (4 tools)
- [Key Management](key-management.md) — Manage FPE encryption keys and tweaks (9 tools)

## Reference

- [Support Read-Only Mode](support-mode.md) — `SUPPORT_MODE` and the `enter_support_mode` / `request_write_unlock` / `exit_support_mode` tools: expose only the 77 lookup tools (78 on stdio, counting an inert `enter_support_mode`), for support and field engineering investigations
- [Troubleshooting Prompts](support-mode.md#publishing-the-prompts) — eight symptom-based prompts served over `prompts/list`, each arming support mode as its first step
- [Error Handling](error-handling.md) — Error types, retry behavior, and response structure
- [Logging](logging.md) — What is logged at each level, and which arguments are redacted
- [Releasing](releasing.md) — Tagging a release, what the publish workflow checks, and the `git` prerequisite for builds

## Common Patterns

All tools return structured responses:

```json
{"success": true, "data": {...}, "error": null}
```

On failure:

```json
{"success": false, "data": null, "error": "error message"}
```

Parameters that accept lists (rules, classifier names, audit filters) also accept JSON strings for CLI compatibility.

## Databricks Quick Reference

For `create_policy` against a Databricks metastore you MUST pass:

- `policy_type="PUSHDOWN"` (the API rejects `"TAG"` for Databricks)
- `database_ids=[<id>]` as a list — even when targeting a single database (e.g. `[2167]`)
- `tag` as the raw column tag name (no `connect_tag` step; Databricks tags do not appear in `get_tags`)

See [Policies & Rules](policies.md) for details.
