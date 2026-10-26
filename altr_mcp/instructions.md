ALTR MCP server for managing data security on Snowflake, Databricks, and OLTP databases. Provides tools for database connections, tag management, masking policy and rule CRUD, automated data classification, role discovery, access management, audits, telemetry, and sidecar configuration.

IMPORTANT: Classification jobs (create_job, create_gdlp_job, create_databricks_job) are async and can take 10-30+ minutes. After creating a job, stop and tell the user to wait for completion. Poll with get_jobs until status is COMPLETED before calling get_classification_report.

IMPORTANT: GDLP (Google DLP) classification is a SEPARATE job type from ALTR-native classification. GDLP does NOT use classifier collections — it calls Google DLP's API directly. Use `create_gdlp_job` (Snowflake) or `create_databricks_job` (Databricks) for GDLP scans. Use `create_job` with a `collection_name` only for ALTR-native regex-based classification.

IMPORTANT: TAG HANDLING DIFFERS BY PLATFORM. Snowflake and Databricks tags are fundamentally different objects in ALTR — do not confuse them.

- **Snowflake tags are first-class connected objects in ALTR.** Each tag is registered to ALTR via `connect_tag`, which creates a persistent tag object with a `tag_group_id`, masking configuration, allowed values, and platform metadata. After connection, the tag is listed by `get_tags`, inspected with `get_tag_details*`, edited with `update_tag`, and disconnected with `disconnect_tag` / `disconnect_tag_by_details`. When creating a masking policy, you pass the UPPERCASE name of an already-connected tag to `create_policy` and omit `database_ids`. A Snowflake tag that was created in Snowflake but never connected to ALTR will NOT appear in `get_tags` and CANNOT be used in a policy.
- **Databricks tags are NOT objects in ALTR — they are just raw string references.** There is no Databricks equivalent of `connect_tag`; there is no Databricks `tag_group_id`; Databricks tags will NEVER appear in `get_tags`, `get_tag_details`, or `get_tag_details_by_group_id`, and the `update_tag` / `disconnect_tag*` tools do not apply to them. To apply masking on Databricks, you pass the raw column tag name string directly to `create_policy` along with `policy_type="PUSHDOWN"` and `database_ids` as a list. `database_ids` is REQUIRED for Databricks policies and is ALWAYS a list — even when targeting a single database, wrap the ID in a list (e.g., `database_ids=[2167]`, never a bare int). Using `policy_type="TAG"` or omitting `database_ids` for a Databricks policy will be rejected by the API.

In short: for Snowflake, the tag is a managed ALTR object you must register first; for Databricks, the tag is just a name string you reference at policy-creation time.

MASKING LEVELS (use these exact values with add_rules):
10000 = No Mask, 10001 = Full Mask, 10002 = Email Mask, 10003 = Show Last Four, 10004 = Constant Mask, 10005 = Null, 10006 = Full Mask Hash, 10007 = Email Hash, 10008 = Show Last Four Hash, 10009 = Constant Date. There are exactly 10 masking levels (10000-10009). Do NOT claim any level is invalid or unsupported.

TOOL USAGE GUIDANCE

Most tools are named <verb>_<object>. These verbs recur, and each carries a
consistent meaning:

  get_ / list_           read; safe to call freely
  create_ / add_         create something new
  update_                modify in place
  connect_               register an object that already exists in Snowflake,
                         Databricks, or a database, so ALTR can manage it
  register_              add a new entry to an ALTR-side registry
  disconnect_            stop managing a connected object; the database, tag,
                         or repo itself continues to exist on its platform
  deregister_ / delete_  destroy the object
  trigger_               start an asynchronous operation
  search_                start an audit query; retrieve results with the
                         matching get_*_results tool, using the search_uuid
                         or token it returns

Two things this table does not cover. Verbs outside this table — approve_,
deny_, cancel_, confirm_, archive_, restore_, deactivate_, rotate_, record_,
revoke_, pin_, unpin_, import_, remove_ — mean what they say; read the tool
description. And the tokenization domains put the domain first rather than
the verb: vault_tokenize, critical_delete_tokens. Read the verb after that
prefix, and note that both domains can delete tokens irreversibly.

The disconnect_/delete_ split is deliberate: disconnect_database leaves the
database untouched, while delete_policy destroys the policy. Objects that
exist only inside ALTR — sidecar listeners and bindings — are destroyed, not
disconnected, whichever verb their name uses.

Sidecar configuration tools carry an sc_ infix (list_sc_repos,
create_sc_sidecar) to distinguish them from similarly named tools elsewhere.

The 13 domains:

  Databases              connect Snowflake, OLTP, and Databricks data sources;
                         also get_service_users for Snowflake keypair auth
  Tags                   register Snowflake tags with ALTR for masking
  Policies & Rules       masking policies and per-role masking levels;
                         also get_roles
  Classification         scans for sensitive columns — classifiers,
                         collections, jobs, findings, review decisions
  Access Management      Snowflake and OLTP access management policies
  Access Requests        submit, approve, deny, and cancel access requests
  Audits                 sidecar, Snowflake query, and system audit search
  Audit Reports          scheduled report definitions and instances,
                         comments, sign-offs
  Telemetry              agent and sidecar instance health
  Sidecar Configuration  sidecar proxy agents, repos, repo users, sidecar
                         service users, sidecars, listeners, bindings
  Vault Tokenization     tokenize, detokenize, and permanently delete tokens
                         held in the ALTR vault
  Critical Tokenization  the same operations against the critical token store,
                         for the highest-sensitivity values
  Key Management         format-preserving encryption keys and tweaks

Individual tools are not listed here — the tool list you already have carries
every name and description, and it is authoritative. Use the domains above to
decide where to look and the verb table to predict what a tool will do.

Common workflow (end-to-end Snowflake setup):

  1. Discover existing state — databases, tags, policies, roles
  2. Run a classification job to find sensitive columns
     - ALTR-native (regex classifiers): create_job — requires collection_name
     - GDLP (Google DLP): create_gdlp_job — requires only database_id, no collection
     IMPORTANT: Classification jobs are async and can take 10-30+ minutes.
     After creating a job, STOP and tell the user to wait for it to finish.
     Do NOT proceed until get_jobs shows status COMPLETED.
  3. Review the classification report (get_classification_report)
  4. Check if the needed Snowflake tags already exist using get_tags.
     This server connects existing Snowflake tags to ALTR — it does not
     create tags in Snowflake. If tags are missing, instruct the user to
     create them in Snowflake first (via the Snowflake console, SQL, or
     another MCP server like snowflake-labs-mcp).
  5. Connect Snowflake tags to ALTR (connect_tag)
  6. Create masking policies (create_policy) and add rules (add_rules)

Common workflow (Databricks setup):

  1. Connect the workspace — create_databricks_database
  2. Get the database ID — get_databases (use the numeric id field)
  3. Run a GDLP classification scan — create_databricks_job
     Wait for completion via get_jobs, then review with get_classification_report
  4. Create a PUSHDOWN masking policy — create_policy(tag="<raw_tag_name>",
     policy_type="PUSHDOWN", database_ids=[<id>])
     Tag name is any string — no connect_tag step needed for Databricks.
     IMPORTANT: policy_type MUST be "PUSHDOWN" for Databricks; "TAG" is rejected.
     IMPORTANT: database_ids is REQUIRED and MUST be a list, even for a
     single database (e.g., database_ids=[2167]).
  5. Add masking rules — add_rules

These steps are not always required in order — users may skip classification
if they already know which columns to tag, or they may only need to add rules
to an existing policy. Adapt to what the user asks for.
