# Classification Tools (41 tools)

Discover sensitive data in your databases using automated classification. Manage classifiers (pattern-based detectors), group them into collections, and run classification jobs that scan columns for PII, financial data, and other sensitive patterns. Supports Snowflake, OLTP, and Databricks (GDLP only).

## Tool Summary

| Tool | Description |
|------|-------------|
| `get_classifiers` | List all available data classifiers |
| `get_classifier` | Get details for a single classifier |
| `create_classifier` | Create a custom classifier defined by a compound ruleset |
| `update_classifier` | Update an existing custom classifier |
| `delete_classifier` | Remove a custom classifier |
| `get_collections` | List classifier collections |
| `get_collection` | Get details for a single collection |
| `create_collection` | Create a classifier collection |
| `update_collection` | Update a collection's description |
| `delete_collection` | Delete a classifier collection |
| `get_collection_classifiers` | List classifiers in a collection |
| `add_classifiers_to_collection` | Add classifiers to a collection |
| `remove_classifiers_from_collection` | Remove classifiers from a collection |
| `import_altr_managed_classifiers` | Sync ALTR prebuilt classifiers into your org |
| `get_altr_managed_timestamp` | Check if a newer version of ALTR classifiers is available |
| `list_altr_managed_classifiers` | List available ALTR-managed (prebuilt) classifiers |
| `get_jobs` | Check status of classification jobs |
| `get_active_jobs` | List all currently running or paused jobs |
| `get_job` | Get details for a single job |
| `get_job_summary` | Get per-classifier detection counts for a completed job |
| `create_job` | Run an ALTR-native classification scan (Snowflake) |
| `create_gdlp_job` | Run a GDLP (Google DLP) scan on a Snowflake connection |
| `create_databricks_job` | Run a GDLP scan on a Databricks connection |
| `create_oltp_job` | Run an on-demand scan on an OLTP sidecar repo |
| `update_job_status` | Pause, cancel, or resume a job |
| `get_job_findings` | List databases with detected columns (findings tree entry point) |
| `get_job_findings_schemas` | List schemas with detections in a database |
| `get_job_findings_tables` | List tables with detections in a schema |
| `get_job_findings_columns` | List detected columns in a table |
| `get_job_findings_classifiers` | List classifiers that fired on a column |
| `get_job_findings_lineage` | Get compound-ruleset evaluation trace for a classifier on a column |
| `get_job_findings_leaves` | List every finding in a job in one paginated stream |
| `record_job_decision` | Approve or reject classification findings |
| `get_job_decisions` | List review decisions recorded for a job |
| `revoke_job_decisions` | Remove previously recorded decisions |
| `record_bulk_job_decision` | Approve or reject every undecided finding matching a filter |
| `revoke_bulk_job_decision` | Undo a bulk decision |
| `get_job_review_status` | Get approved/rejected/pending counts for a job |
| `confirm_job_report` | Confirm a review-gated job's decisions and release its report |
| `cancel_job_report` | Cancel a review-gated job before its report is confirmed |
| `get_classification_report` | Download full results from a completed job |

## Typical Workflow

### Snowflake (ALTR-native)

1. Check existing classifiers with `get_classifiers` and collections with `get_collections`
2. Optionally create custom classifiers and collections (or call `import_altr_managed_classifiers` to sync prebuilts)
3. Get the target database ID with `get_database_id`
4. Run a scan with `create_job`
5. Wait 15-30+ minutes, then check status with `get_jobs`
6. When status is COMPLETED, browse results with `get_job_findings` or download with `get_classification_report`
7. Optionally record human review decisions with `record_job_decision` and track progress with `get_job_review_status`

### Databricks

1. Get the Databricks database ID with `get_database_id`
2. Run a GDLP scan with `create_databricks_job` (optionally pass `collection_name` to scope the scan to a collection's classifiers)
3. Wait, then check status with `get_jobs`
4. When COMPLETED, view results with `get_job_findings` or `get_classification_report`

### OLTP (sidecar repos)

1. Find the CLASSIFIER agent with `list_sc_agents` (`agent_type="CLASSIFIER"`), and the target repo and service user with `list_sc_repos` / `list_sc_service_users`
2. Run an on-demand scan with `create_oltp_job` (sidecar repos have no `database_id`, so `create_job` does not apply)
3. To enable METADATA column-name matching or AMAZON_COMPREHEND entity detection, pass those values in `condition_types`
4. Wait, then check status with `get_jobs`
5. When COMPLETED, view results with `get_job_findings` or `get_classification_report`

For Snowflake GDLP (Google DLP) scans, use `create_gdlp_job` instead of `create_job`.

### Review-gated jobs

Every job-creation tool accepts `requires_review`. When it is true, the job holds its report for human review:

1. Create the job with `requires_review=true`
2. When the job reaches AWAITING_REVIEW, browse findings with `get_job_findings` or `get_job_findings_leaves`
3. Decide findings with `record_job_decision`, or many at once with `record_bulk_job_decision` (run it with `dry_run=true` first to see the counts)
4. Check that nothing is pending with `get_job_review_status`
5. Release the report with `confirm_job_report`; decisions are then locked. Poll `get_job` until COMPLETED, then use `get_classification_report`

To abandon a review instead, call `cancel_job_report`.

## Condition Types

Every job creation tool accepts an optional `condition_types` list: the full set of evaluation targets for the scan. When it is omitted, the server picks a default for the job type. A list replaces that default rather than adding to it, so include every target your classifiers use. An omitted target is not evaluated, and its conditions count as passing within an AND.

| Value | Description |
|-------|-------------|
| `ROW_DATA` | Regex-based sampling of column values (default) |
| `METADATA` | Evaluate column name/description against classifier rules |
| `COLUMN_LOCATION` | Scope evaluation by database/schema/table location |
| `CONTENT_TYPE` | Detect structured/binary content formats (JSON, PDF, ZIP, etc.) |
| `DATA_LENGTH` | Evaluate UTF-8 byte length of column values |
| `COLUMN_SIZE` | Evaluate the declared column size |
| `AMAZON_COMPREHEND` | AWS Comprehend PII entity detection (requires compound-ruleset classifier) |
| `GDLP` | Google DLP info-type detection |
| `ENTROPY` | Flag columns whose sampled values look like secret keys (needs row sampling) |

`AMAZON_COMPREHEND` never runs by default. `GDLP` runs by default on GDLP and Databricks jobs and on OLTP jobs with `classification_type` 6; list it in `condition_types` to enable it elsewhere.

## Classification Types

The `classification_type` parameter used across job tools maps to:

| Code | Description |
|------|-------------|
| `1` | Google DLP |
| `2` | Snowflake Native |
| `3` | Snowflake Object Tag Import |
| `4` | Snowflake Native + Tag Import |
| `5` | ALTR Native (regex) — default for `create_oltp_job` |
| `6` | GDLP BYOK (bring-your-own-key) |

## Tool Details

### get_classifiers

List all available data classifiers (pattern-based detectors) in ALTR. Includes both ALTR-managed and custom classifiers.

**Parameters:** None

---

### get_classifier

Get details for a single classifier by name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `classifier_name` | str | yes | Exact classifier name as returned by `get_classifiers` |

---

### create_classifier

Create a custom data classifier defined by a compound ruleset: one or more conditions (ROW_DATA regex, METADATA, AMAZON_COMPREHEND, DATA_LENGTH, CONTENT_TYPE and more) combined with AND/OR. A plain regex classifier is a ruleset with a single ROW_DATA condition carrying the pattern and its `minimum_threshold`. Sampling is set on the job, not the classifier.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `classifier_name` | str | yes | Unique name for the classifier |
| `compound_ruleset` | dict | yes | Nested AND/OR condition tree |
| `description` | str | no | Human-readable explanation of what it detects |

**Compound ruleset structure:**
```json
{
  "operator": "AND",
  "conditions": [
    {
      "target": "ROW_DATA",
      "pattern": "\\d{3}-\\d{2}-\\d{4}",
      "comparator": "matches",
      "minimum_threshold": 70
    },
    {
      "target": "METADATA",
      "pattern": "ssn",
      "comparator": "contains"
    }
  ]
}
```

**AMAZON_COMPREHEND leaf fields:** `entity_type` (e.g. `"SSN"`, `"CREDIT_DEBIT_NUMBER"`, `"EMAIL"`), `minimum_score` (0.0–1.0, default `0.5`).

**METADATA leaf fields:** `comparator` (`matches`/`contains`/`equals`/`starts_with`/`ends_with`), `pattern`.

**DATA_LENGTH / COLUMN_SIZE leaf fields:** `length` or `size`, numeric `comparator` (`greater_than`/`less_than`/`equals`/etc.), optional `trim`.

**ENTROPY leaf fields** (flags values that look like secret keys): `minimum_evidence_bits`, `minimum_key_bits`, `alphabet_classes`, `decode_base64`, `cumulative`.

Always set `minimum_threshold` on ROW_DATA leaves. All conditions support `negated: true`.

---

### update_classifier

Update an existing custom classifier. Only provided fields are changed. Passing `compound_ruleset` also removes any legacy top-level pattern, so the ruleset alone decides matches. To keep a legacy regex, include it as a ROW_DATA condition with its own `minimum_threshold`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `classifier_name` | str | yes | Exact classifier name to update |
| `description` | str | no | Updated description |
| `compound_ruleset` | dict | no | Updated compound ruleset |

---

### delete_classifier

Remove a custom classifier you created. Cannot delete ALTR-managed classifiers.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `classifier_name` | str | yes | Exact classifier name as returned by `get_classifiers` |

---

### get_collections

List classifier collections (groups of classifiers used for classification jobs). A collection is required when creating a job with `create_job`.

**Parameters:** None

---

### get_collection

Get details for a single collection by name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Exact collection name as returned by `get_collections` |

---

### create_collection

Create a classifier collection to use for automated data discovery.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Unique name for the collection |
| `description` | str | no | Human-readable description. Default: `""` |

---

### update_collection

Update a collection's description.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Exact collection name to update |
| `description` | str | yes | Updated description |

---

### delete_collection

Delete a classifier collection. Cannot delete collections in use by active or recent jobs.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Exact collection name as returned by `get_collections` |

---

### get_collection_classifiers

List classifiers that belong to a collection.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Collection name to inspect |
| `limit` | int | no | Max items to return |
| `contiguous_id` | str | no | Pagination token |

---

### add_classifiers_to_collection

Add classifiers to an existing collection. All classifiers must already exist. ALTR-managed collections cannot have classifiers appended.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Collection to add classifiers to |
| `classifier_names` | str or list[str] | yes | Classifier name(s) to add |

---

### remove_classifiers_from_collection

Remove classifiers from a collection.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_name` | str | yes | Collection to remove classifiers from |
| `classifier_names` | str or list[str] | yes | Classifier name(s) to remove |

---

### import_altr_managed_classifiers

Import all ALTR-managed classifiers and create/update the "ALTR Managed" collection. ALTR maintains a curated set of classifiers for common sensitive data types (SSN, credit cards, email, phone numbers, etc.). Use `get_altr_managed_timestamp` first to check if an update is available.

**Parameters:** None

---

### get_altr_managed_timestamp

Check whether a newer version of ALTR-managed classifiers is available. Returns the latest available version timestamp alongside the version currently installed in your org.

**Parameters:** None

---

### list_altr_managed_classifiers

List available ALTR-managed (prebuilt) classifiers. Shows the canonical set maintained by ALTR; call `import_altr_managed_classifiers` to sync them into your org.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | no | Max items to return |
| `contiguous_id` | str | no | Pagination token |

---

### get_jobs

Check the status of classification jobs. Jobs run asynchronously and can take 10-30+ minutes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | no | Max jobs to return (default 50, max 50) |
| `contiguous_id` | str | no | Pagination token from a prior call |
| `status` | str | no | Filter by status: `RUNNING`, `PAUSED`, `COMPLETED`, `CANCELLED`, `FAILED` |
| `job_type` | str | no | Filter by type: `FULL` or `INCREMENTAL` |
| `database_id` | int | no | Restrict to a specific database |
| `agent_id` | str | no | Restrict to jobs run by a specific CLASSIFIER agent UUID |
| `classification_type` | int | no | Filter by type code (1–6; see [Classification Types](#classification-types)) |
| `order` | str | no | Sort order by start time: `asc` or `desc` (default `desc`) |

---

### get_active_jobs

List all currently active (non-terminal) classification jobs — only RUNNING or PAUSED states. Faster than `get_jobs` when you just want to see what's in flight.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | no | Max jobs to return |
| `contiguous_id` | str | no | Pagination token |
| `database_id` | int | no | Filter by database ID |
| `agent_id` | str | no | Filter by agent UUID |

---

### get_job

Get details for a single classification job by ID.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier from a create-job tool or `get_jobs` |

---

### get_job_summary

Get an inline per-classifier detection count summary for a completed job. Faster than `get_classification_report` because it skips the presigned S3 round-trip.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | COMPLETED job identifier |

---

### create_job

Run an ALTR-native classification scan on a Snowflake database. Jobs run asynchronously; poll with `get_jobs` and view results with `get_job_findings` or `get_classification_report`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_type` | str | yes | Job type: `FULL` or `INCREMENTAL` |
| `database_id` | int | yes | Target database ID (from `get_databases` / `get_database_id`) |
| `collection_name` | str | yes | Classifier collection to use for this run |
| `condition_types` | list[str] | no | Full set of condition targets to evaluate; replaces the server default (see [Condition Types](#condition-types)) |
| `requires_review` | bool | no | Hold the report for human review until `confirm_job_report` runs (see [Review-gated jobs](#review-gated-jobs)) |

---

### create_gdlp_job

Run a GDLP (Google DLP) classification scan on a Snowflake connection. Posts to the same `/v1/jobs/snowflake` endpoint as `create_job`, differentiated by classification type; always runs a FULL scan. Jobs run asynchronously.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_id` | int | yes | ALTR database ID for the Snowflake connection |
| `collection_name` | str | no | Any ALTR collection whose classifiers scope this scan (not limited to GDLP collections) — every classifier in it is evaluated, subject to `condition_types`. When omitted, all default Google DLP infoTypes are used |
| `condition_types` | list[str] | no | Full set of condition targets to evaluate; replaces the server default of `GDLP`, `METADATA`, `COLUMN_LOCATION`, `CONTENT_TYPE` |
| `sample_size` | int | no | Rows to sample per column, or a percentage when `sample_type` is `PERCENT` (server defaults to 100) |
| `sample_type` | str | no | Sampling unit: `ROWS` (a fixed count, the server default) or `PERCENT` |
| `requires_review` | bool | no | Hold the report for human review until `confirm_job_report` runs (see [Review-gated jobs](#review-gated-jobs)) |

---

### create_databricks_job

Run a GDLP classification scan on a Databricks connection. Scans all accessible catalogs and tables in the connected workspace. Jobs run asynchronously.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_id` | int | yes | ALTR database ID for the Databricks connection |
| `collection_name` | str | no | Any ALTR collection whose classifiers scope this scan (not limited to GDLP collections) — every classifier in it is evaluated, subject to `condition_types`. When omitted, all default Google DLP infoTypes are used |
| `condition_types` | list[str] | no | Condition targets to evaluate (server defaults to `["GDLP", "METADATA", "COLUMN_LOCATION", "CONTENT_TYPE"]`) |
| `requires_review` | bool | no | Hold the report for human review until `confirm_job_report` runs (see [Review-gated jobs](#review-gated-jobs)) |

---

### create_oltp_job

Run an on-demand classification scan on an OLTP database (Oracle, MSSQL, MySQL, PostgreSQL) via a sidecar classification agent. Use this for OLTP sidecar repos — `create_job` requires a numeric `database_id` that sidecar repos do not have. Jobs run asynchronously.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | str | yes | CLASSIFIER agent UUID (from `list_sc_agents` with `agent_type="CLASSIFIER"`) |
| `repo_name` | str | yes | Target sidecar repository name (from `list_sc_repos`) |
| `service_user_name` | str | yes | Repo service user the agent authenticates as (from `list_sc_service_users`) |
| `collection_name` | str | yes | Classifier collection to run |
| `classification_type` | int | no | Type code: `5` (ALTR Native, default) or `6` (GDLP BYOK) |
| `sample_strategy` | str | no | `ROWS`, `METADATA`, or `COMBINED`. Default `ROWS`; GDLP BYOK supports `ROWS` only |
| `sample_size` | int | no | Rows sampled per column (default `1000`), or a percentage from 1 to 100 when `sample_type` is `PERCENT`, where it is required. Not sent for `METADATA` |
| `sample_type` | str | no | Sampling unit: `ROWS` (a fixed count, default) or `PERCENT`. Not sent for `METADATA` |
| `condition_types` | list[str] | no | Full set of condition targets to evaluate; replaces the default derived from `sample_strategy` and `classification_type`. `AMAZON_COMPREHEND` must be listed to run; `GDLP` is included by default only for `classification_type` 6 |
| `sid` | str | no | Oracle SID (Oracle repos only) |
| `service_name` | str | no | Oracle service name or alternate connection identifier |
| `task_id` | str | no | Link this on-demand run to an existing scheduled task UUID |
| `requires_review` | bool | no | Hold the report for human review until `confirm_job_report` runs (see [Review-gated jobs](#review-gated-jobs)) |

---

### update_job_status

Control a running classification job (pause, cancel, or resume).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier to update |
| `status` | str | yes | New status: `PAUSED`, `CANCELLED`, or `RUNNING` |

---

### get_job_findings

Entry point for navigating classification results hierarchically. Returns databases that contain detected columns. Drill down with `get_job_findings_schemas` → tables → columns → classifiers. Prefer this over `get_classification_report` when you want to interactively filter or explore results.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `limit` | int | no | Max databases to return |
| `page_token` | str | no | Pagination token |
| `classifier_name` | str or list[str] | no | Filter to databases with detections by these classifier(s) |
| `confirmed_status` | str | no | Filter by review status: `approved`, `rejected`, or `pending` |
| `include_column_status_counts` | bool | no | Include approved/rejected/pending counts per database |

---

### get_job_findings_schemas

List schemas with detected columns in a database. Second level of the findings tree.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `database` | str | yes | Database name from `get_job_findings` |
| `limit` | int | no | Max schemas to return |
| `page_token` | str | no | Pagination token |
| `classifier_name` | str or list[str] | no | Filter by classifier name(s) |
| `confirmed_status` | str | no | Filter by review status |

---

### get_job_findings_tables

List tables with detected columns in a schema. Third level of the findings tree.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `database` | str | yes | Database name |
| `schema` | str | yes | Schema name from `get_job_findings_schemas` |
| `limit` | int | no | Max tables to return |
| `page_token` | str | no | Pagination token |
| `classifier_name` | str or list[str] | no | Filter by classifier name(s) |
| `confirmed_status` | str | no | Filter by review status |

---

### get_job_findings_columns

List detected columns in a table. Fourth level of the findings tree.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `database` | str | yes | Database name |
| `schema` | str | yes | Schema name |
| `table` | str | yes | Table name from `get_job_findings_tables` |
| `limit` | int | no | Max columns to return |
| `page_token` | str | no | Pagination token |
| `classifier_name` | str or list[str] | no | Filter by classifier name(s) |
| `confirmed_status` | str | no | Filter by review status |

---

### get_job_findings_classifiers

List classifiers that fired on a specific column. Use `get_job_findings_lineage` to see why a specific classifier did or did not fire.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `database` | str | yes | Database name |
| `schema` | str | yes | Schema name |
| `table` | str | yes | Table name |
| `column` | str | yes | Column name from `get_job_findings_columns` |
| `limit` | int | no | Max classifiers to return |
| `page_token` | str | no | Pagination token |
| `confirmed_status` | str | no | Filter by review status |

---

### get_job_findings_lineage

Get the full compound-ruleset evaluation trace for a classifier on a specific column. Shows which conditions evaluated, which matched, and why the classifier did or did not fire. Useful for debugging custom classifiers or inspecting AMAZON_COMPREHEND / METADATA condition results.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `database` | str | yes | Database name |
| `schema` | str | yes | Schema name |
| `table` | str | yes | Table name |
| `column` | str | yes | Column name |
| `classifier_name` | str | yes | Classifier name to inspect |

---

### get_job_findings_leaves

List every finding in a job in one paginated stream, one row per (database, schema, table, column, classifier), ordered by full path. Each row carries the finding count, average match rate, whether it is new, and its resolved review status. Use this to see a whole job at once instead of walking the tree. File sources also return crawl records, with an empty `classifier_name` and no `confirmed_status`; they are not findings and need no decision.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |
| `limit` | int | no | Max rows per page (default 100, max 1000) |
| `page_token` | str | no | `next_page_token` from a prior call |
| `confidence` | list[str] | no | Keep only these confidence tiers: `HIGH`, `MEDIUM`, `LOW` |

---

### record_job_decision

Approve or reject classification findings in a job. Decisions can be scoped from the entire job down to a specific classifier on a specific column. Broader scopes apply to all columns and classifiers within.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |
| `confirmed_status` | str | yes | Decision: `approved` or `rejected` |
| `database` | str | no | Scope to this database |
| `schema` | str | no | Scope to this schema (requires `database`) |
| `table` | str | no | Scope to this table (requires `schema`) |
| `column` | str | no | Scope to this column (requires `table`) |
| `classifier_name` | str | no | Scope to this classifier (requires `column`) |

---

### get_job_decisions

List human review decisions recorded for a classification job.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |
| `database` | str | no | Filter to this database |
| `schema` | str | no | Filter to this schema |
| `table` | str | no | Filter to this table |
| `column` | str | no | Filter to this column |
| `limit` | int | no | Max decisions to return |
| `page_token` | str | no | Pagination token |

---

### revoke_job_decisions

Remove previously recorded review decisions. Revoked findings return to `pending` status. Scope works the same as `record_job_decision`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |
| `database` | str | no | Scope to this database |
| `schema` | str | no | Scope to this schema |
| `table` | str | no | Scope to this table |
| `column` | str | no | Scope to this column |
| `classifier_name` | str | no | Scope to this classifier |

---

### record_bulk_job_decision

Approve or reject every undecided finding that matches a filter: the given classifiers, optionally narrowed by confidence tier and by a database, schema and table path. Findings that already have a decision are left alone, and each covered finding can still be overridden with `record_job_decision`. Returns the matched counts, plus a `bulk_decision_id` when something was recorded (not on a dry run or when nothing matched). `classifier_names` must name at least one classifier.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |
| `confirmed_status` | str | yes | Decision: `approved` or `rejected` |
| `classifier_names` | list[str] | yes | Classifiers whose findings to decide |
| `confidence` | list[str] | no | Keep only these confidence tiers: `HIGH`, `MEDIUM`, `LOW` |
| `database` | str | no | Limit to this database |
| `schema` | str | no | Limit to this schema (requires `database`) |
| `table` | str | no | Limit to this table (requires `schema`) |
| `dry_run` | bool | no | Return the counts without recording anything (default false) |

---

### revoke_bulk_job_decision

Undo a bulk decision. Revokes every decision it still covers; a finding decided individually afterwards keeps that individual decision.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |
| `bulk_decision_id` | str | yes | `bulk_decision_id` returned by `record_bulk_job_decision` |

---

### get_job_review_status

Get the review progress for a job — total/approved/rejected/pending counts across all findings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Identifier of a COMPLETED job, or of a review-gated job at AWAITING_REVIEW |

---

### confirm_job_report

Confirm the review of a review-gated job (created with `requires_review=true`) and release its report. Every finding must have a decision; check with `get_job_review_status` first. Report generation then runs in the background and decisions are locked. Poll `get_job` until COMPLETED, then read the report with `get_classification_report`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |

---

### cancel_job_report

Cancel a review-gated job that is still being reviewed. The job moves to CANCELLED and its review data is discarded. A job whose report has already been confirmed cannot be cancelled this way.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier |

---

### get_classification_report

Download full results from a completed classification job as JSON. Returns which columns were detected as containing sensitive data along with confidence scores. For interactive exploration, prefer `get_job_findings`.

After reviewing results, check if needed Snowflake tags exist using `get_tags`. If tags are missing, create them in Snowflake before connecting with `connect_tag`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | str | yes | Job identifier from a create-job tool or `get_jobs` |
