import urllib.parse

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from altr_mcp.settings import get_settings
from altr_mcp.utils import classification
from altr_mcp.utils.logging import log_tool


def register(mcp: FastMCP) -> None:

    # ── Classifiers ─────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_classifiers() -> dict:
        """List all available data classifiers in ALTR.

        Classifiers automatically detect sensitive data
        types like SSNs, emails,
        and phone numbers. Includes both ALTR-managed and custom classifiers.
        """
        settings = get_settings()
        classifiers = await classification.get_classifiers(
            {}, settings.auth)
        return {"success": True, "data": classifiers, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_classifier(classifier_name: str) -> dict:
        """Get details for a single classifier by name.

        Args:
            classifier_name: Exact classifier name as returned
                by `get_classifiers`.
        """
        settings = get_settings()
        response = await classification.get_classifier(
            classifier_name, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_classifier(
            classifier_name: str,
            compound_ruleset: dict,
            description: str | None = None
            ) -> dict:
        """Create a custom data classifier defined by a compound ruleset.

        All detection logic lives in `compound_ruleset`: one or more
        conditions (ROW_DATA regex, METADATA column-name matching,
        AMAZON_COMPREHEND entity detection, DATA_LENGTH, CONTENT_TYPE, GDLP
        info-types and more) combined with AND/OR. A plain regex classifier
        is a ruleset with a single ROW_DATA condition carrying the pattern
        and its minimum_threshold. Always set minimum_threshold on ROW_DATA
        leaves. Sampling is set on the job, not here.

        Compound ruleset structure:
        ```json
        {
          "operator": "AND",
          "conditions": [
            {
              "target": "ROW_DATA",
              "pattern": "\\\\d{3}-\\\\d{2}-\\\\d{4}",
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

        Valid `target` values: ROW_DATA, METADATA, COLUMN_LOCATION, GDLP,
        SNOWFLAKE_NATIVE, CONTENT_TYPE, DATA_LENGTH, COLUMN_SIZE,
        AMAZON_COMPREHEND, ENTROPY.

        AMAZON_COMPREHEND leaf fields: `entity_type` (e.g. "SSN", "CREDIT_DEBIT_NUMBER",
        "EMAIL"), `minimum_score` (0.0–1.0, default 0.5).

        METADATA leaf fields: `comparator` (matches/contains/equals/starts_with/
        ends_with), `pattern`.

        DATA_LENGTH / COLUMN_SIZE leaf fields: `length` or `size`, numeric
        `comparator` (greater_than/less_than/equals/etc.), optional `trim`.

        CONTENT_TYPE leaf fields: `content_format` or `content_formats` (list),
        `dominance_threshold`. Formats: JSON, XML, CSV, PDF, DOCX, XLSX, PNG,
        JPEG, ZIP, GZIP, PARQUET, and more.

        ENTROPY leaf fields (flags values that look like secret keys):
        `minimum_evidence_bits`, `minimum_key_bits`, `alphabet_classes`,
        `decode_base64`, `cumulative`.

        All leaf conditions support `negated: true`.

        Args:
            classifier_name: Unique name for the classifier.
            compound_ruleset: Nested AND/OR condition tree, as above.
            description: Human-readable explanation of what it detects.
        """
        settings = get_settings()
        params = {
            "classifier_name": classifier_name,
            "description": description,
            "compound_ruleset": compound_ruleset,
        }
        response = await classification.create_classifier(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def update_classifier(
            classifier_name: str,
            description: str | None = None,
            compound_ruleset: dict | None = None
            ) -> dict:
        """Update an existing custom classifier. Only provided fields are changed.

        Passing `compound_ruleset` also removes any legacy top-level pattern,
        so the ruleset alone decides matches. To keep a legacy regex, include
        it as a ROW_DATA condition with its own minimum_threshold.

        Args:
            classifier_name: Exact classifier name to update.
            description: Updated description.
            compound_ruleset: Updated compound ruleset. See `create_classifier`
                for structure and valid condition targets.
        """
        settings = get_settings()
        data = {}
        if description is not None:
            data["description"] = description
        if compound_ruleset is not None:
            data["compound_ruleset"] = compound_ruleset
            # A null pattern removes a legacy top-level pattern on the API.
            # Keep the classifier threshold: Snowflake reads 0 as match-all.
            data["pattern"] = None
        response = await classification.update_classifier(
            classifier_name, data, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    @log_tool
    async def delete_classifier(classifier_name: str) -> dict:
        """Remove a custom classifier you created.

        Cannot delete ALTR managed classifiers. Only use for
        classifiers you created with `create_classifier`.

        Args:
            classifier_name: Exact classifier name as returned
                by `get_classifiers`.
        """
        settings = get_settings()
        params = {"classifier_name": classifier_name}
        response = await classification.delete_classifier(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── Collections ─────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_collections() -> dict:
        """List classifier collections (groups of classifiers
        used for classification jobs).

        A collection is required when creating a classification
        job with `create_job`. Check for existing collections
        (e.g., "ALTR Managed") before creating new ones.
        """
        settings = get_settings()
        collections = await classification.get_collections(
            {}, settings.auth)
        return {"success": True, "data": collections, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_collection(collection_name: str) -> dict:
        """Get details for a single collection by name.

        Args:
            collection_name: Exact collection name as returned
                by `get_collections`.
        """
        settings = get_settings()
        response = await classification.get_collection(
            collection_name, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_collection(
            collection_name: str,
            description: str = ""
            ) -> dict:
        """Create a classifier collection to use for automated data discovery.

        Collections group classifiers together for
        classification jobs. After creating a collection,
        you can run a classification job to automatically
        scan your database columns and identify which
        contain sensitive data patterns.

        Typical workflow: Create a collection (or use
        existing "ALTR Managed"), then use it in
        `create_job` to scan your database. Review results
        with `get_classification_report` to see which
        columns were detected.

        Args:
            collection_name: Unique name for the collection.
            description: Optional human-readable description.
        """
        settings = get_settings()
        params = {
            "collection_name": collection_name,
            "description": description,
        }
        response = await classification.create_collection(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def update_collection(
            collection_name: str,
            description: str
            ) -> dict:
        """Update a collection's description.

        Args:
            collection_name: Exact collection name to update.
            description: Updated description.
        """
        settings = get_settings()
        response = await classification.update_collection(
            collection_name, {"description": description}, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    @log_tool
    async def delete_collection(collection_name: str) -> dict:
        """Delete a classifier collection.

        Cannot delete collections that are in use by active
        or recent jobs. Only delete collections you created
        that are no longer needed.

        Args:
            collection_name: Exact collection name as returned
                by `get_collections`.
        """
        settings = get_settings()
        params = {"collection_name": collection_name}
        response = await classification.delete_collection(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_collection_classifiers(
            collection_name: str,
            limit: int | None = None,
            contiguous_id: str | None = None
            ) -> dict:
        """List classifiers that belong to a collection.

        Args:
            collection_name: Collection name to inspect.
            limit: Max items to return.
            contiguous_id: Pagination token.
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if contiguous_id is not None:
            params["contiguous_id"] = contiguous_id
        response = await classification.get_collection_classifiers(
            collection_name, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def add_classifiers_to_collection(
            collection_name: str,
            classifier_names: str | list[str]
            ) -> dict:
        """Add classifiers to an existing collection.

        All classifiers must already exist and not already be in the
        collection. ALTR managed collections cannot have classifiers
        appended.

        Args:
            collection_name: Collection to add classifiers to.
            classifier_names: Classifier name(s) to add. Pass a single
                string or a list of strings.
        """
        if isinstance(classifier_names, str):
            classifier_names = [classifier_names]
        settings = get_settings()
        response = await classification.append_classifiers_to_collection(
            collection_name, classifier_names, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def remove_classifiers_from_collection(
            collection_name: str,
            classifier_names: str | list[str]
            ) -> dict:
        """Remove classifiers from a collection.

        Args:
            collection_name: Collection to remove classifiers from.
            classifier_names: Classifier name(s) to remove. Pass a single
                string or a list of strings.
        """
        if isinstance(classifier_names, str):
            classifier_names = [classifier_names]
        settings = get_settings()
        response = await classification.remove_classifiers_from_collection(
            collection_name, classifier_names, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── ALTR-managed classifiers ─────────────────────────────────────────────

    @mcp.tool()
    @log_tool
    async def import_altr_managed_classifiers() -> dict:
        """Import all ALTR-managed classifiers and create/update the
        "ALTR Managed" collection.

        ALTR maintains a curated set of classifiers for common sensitive
        data types (SSN, credit cards, email, phone numbers, etc.). Call
        this to sync the latest prebuilt classifiers into your organization.
        Use `get_altr_managed_timestamp` first to check if an update is
        available before importing.
        """
        settings = get_settings()
        response = await classification.import_altr_managed_classifiers(
            settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_altr_managed_timestamp() -> dict:
        """Check whether a newer version of ALTR-managed classifiers is available.

        Returns the latest available version timestamp alongside the version
        currently installed in your org. If they differ, call
        `import_altr_managed_classifiers` to update.
        """
        settings = get_settings()
        response = await classification.get_altr_managed_timestamp(
            settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def list_altr_managed_classifiers(
            limit: int | None = None,
            contiguous_id: str | None = None
            ) -> dict:
        """List available ALTR-managed (prebuilt) classifiers.

        Shows the canonical set maintained by ALTR, not what's currently
        in your org. Call `import_altr_managed_classifiers` to sync them.

        Args:
            limit: Max items to return.
            contiguous_id: Pagination token.
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if contiguous_id is not None:
            params["contiguous_id"] = contiguous_id
        response = await classification.list_altr_managed_classifiers(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── Jobs ─────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_jobs(
            limit: int | None = None,
            contiguous_id: str | None = None,
            status: str | None = None,
            job_type: str | None = None,
            database_id: int | None = None,
            agent_id: str | None = None,
            classification_type: int | None = None,
            order: str | None = None
            ) -> dict:
        """Check the status of classification jobs you've run.

        Classification jobs run asynchronously and can take
        10-30+ minutes to complete depending on your database
        size. Use this to check if a job has finished after
        waiting an appropriate amount of time.

        Once a job shows status COMPLETED, you can fetch its
        detailed report with `get_classification_report` or
        browse results with `get_job_findings`. If status is
        still RUNNING, wait longer before checking again.

        Typical workflow: After creating a job, wait 15-30+
        minutes, then use this function to check status. When
        status is COMPLETED, use `get_job_findings` to navigate
        results or `get_classification_report` for a full dump.

        Args:
            limit: Max jobs to return (default 50, max 50).
            contiguous_id: Pagination token from a prior
                `get_jobs` call.
            status: Filter by job status (e.g. RUNNING,
                PAUSED, COMPLETED, CANCELLED, FAILED).
            job_type: Filter by job type (FULL or INCREMENTAL).
            database_id: Restrict to a specific database
                (numeric ID from `get_databases` /
                `get_database_id`).
            agent_id: Restrict to jobs run by a specific
                CLASSIFIER agent UUID.
            classification_type: Optional ALTR classification
                type code (1=Google DLP, 2=Snowflake Native,
                3=Snowflake Tag Import, 4=Snowflake Native+Tag Import,
                5=ALTR Native, 6=GDLP BYOK).
            order: Sort order by start time, `asc` or
                `desc` (default `desc`).
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if contiguous_id:
            params["contiguous_id"] = contiguous_id
        if status:
            params["status"] = status
        if job_type:
            params["job_type"] = job_type
        if database_id is not None:
            params["database_id"] = database_id
        if agent_id:
            params["agent_id"] = agent_id
        if classification_type is not None:
            params["classification_type"] = classification_type
        if order:
            params["order"] = order
        jobs = await classification.get_jobs(
            params, settings.auth)
        return {"success": True, "data": jobs, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_active_jobs(
            limit: int | None = None,
            contiguous_id: str | None = None,
            database_id: int | None = None,
            agent_id: str | None = None
            ) -> dict:
        """List all currently active (non-terminal) classification jobs.

        Returns only jobs in RUNNING or PAUSED states. Useful for
        checking what's in flight without filtering through all
        historical jobs.

        Args:
            limit: Max jobs to return.
            contiguous_id: Pagination token.
            database_id: Filter by database ID.
            agent_id: Filter by agent UUID.
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if contiguous_id:
            params["contiguous_id"] = contiguous_id
        if database_id is not None:
            params["database_id"] = database_id
        if agent_id:
            params["agent_id"] = agent_id
        response = await classification.get_active_jobs(params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job(job_id: str) -> dict:
        """Get details for a single classification job by ID.

        Args:
            job_id: Job identifier returned from a create-job tool
                or listed by `get_jobs`.
        """
        settings = get_settings()
        response = await classification.get_job(job_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_summary(job_id: str) -> dict:
        """Get an inline per-classifier classification summary for a completed job.

        Returns classification counts grouped by classifier — faster than
        `get_classification_report` because it doesn't require a presigned
        S3 round-trip. Use this to get a quick count of detected columns
        before drilling into `get_job_findings`.

        Args:
            job_id: Job identifier of a COMPLETED job.
        """
        settings = get_settings()
        response = await classification.get_job_summary(job_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_job(
            job_type: str,
            database_id: int,
            collection_name: str,
            condition_types: list[str] | None = None,
            requires_review: bool | None = None
            ) -> dict:
        """Run an ALTR-native classification scan on a Snowflake database.

        Uses ALTR's own classifiers grouped in a collection.
        This is NOT for GDLP (Google DLP) scans — use `create_gdlp_job`
        for that instead.

        Classification jobs run asynchronously and can take
        10-30+ minutes depending on database size. After
        creating a job, use `get_jobs` to poll for
        completion, then `get_job_findings` or
        `get_classification_report` to view results.

        Args:
            job_type: Job type to run (FULL or INCREMENTAL).
            database_id: Target database ID (from
                `get_databases` / `get_database_id`).
            collection_name: Classifier collection to use for this run.
            condition_types: Optional full set of condition targets to
                evaluate. A list replaces the server default rather than
                adding to it, so include every target your classifiers use;
                an omitted target is not evaluated and its conditions count
                as passing within an AND. Valid values: ROW_DATA, METADATA,
                COLUMN_LOCATION, SNOWFLAKE_NATIVE, CONTENT_TYPE, DATA_LENGTH,
                COLUMN_SIZE, ENTROPY. GDLP and AMAZON_COMPREHEND require
                separate job types.
            requires_review: If true, hold the report for human review. The
                job pauses at AWAITING_REVIEW until every finding is decided
                and `confirm_job_report` runs. Defaults to false.
        """
        settings = get_settings()
        params = {
            "job_type": job_type,
            "database_id": database_id,
            "collection_name": collection_name,
            "condition_types": condition_types,
            "requires_review": requires_review,
        }
        response = await classification.create_job(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_gdlp_job(
            database_id: int,
            collection_name: str | None = None,
            condition_types: list[str] | None = None,
            sample_size: int | None = None,
            sample_type: str | None = None,
            requires_review: bool | None = None
            ) -> dict:
        """Run a GDLP (Google DLP) classification scan on a Snowflake database.

        Uses Google DLP-powered classification hosted by ALTR to detect
        sensitive data. This is distinct from `create_job` (ALTR-native) and
        `create_databricks_job` (Databricks GDLP). Use this when the user asks
        for GDLP classification on Snowflake. Both this tool and `create_job`
        post to the same `/v1/jobs/snowflake` endpoint, differentiated by
        classification type; this one always runs a FULL scan.

        Runs asynchronously — poll with `get_jobs` until status is
        COMPLETED, then fetch results with `get_classification_report`.

        Args:
            database_id: ALTR database ID for the Snowflake connection
                (from `get_databases` / `get_database_id`).
            collection_name: Optional ALTR collection whose classifiers scope
                this scan. Not limited to GDLP collections — every classifier
                in the collection is evaluated (GDLP info-type conditions or
                otherwise), subject to the condition_types evaluation matrix.
                When omitted, all default Google DLP infoTypes are used.
            condition_types: Optional full set of condition targets to
                evaluate. A list replaces the server default (GDLP, METADATA,
                COLUMN_LOCATION, CONTENT_TYPE) rather than adding to it, so
                include every target your classifiers use, GDLP among them.
                Valid values: GDLP, SNOWFLAKE_NATIVE, ROW_DATA, METADATA,
                COLUMN_LOCATION, CONTENT_TYPE, DATA_LENGTH, COLUMN_SIZE,
                AMAZON_COMPREHEND, ENTROPY.
            sample_size: Optional rows to sample per column, or a percentage
                when sample_type is PERCENT (server default 100).
            sample_type: Optional sampling unit: ROWS (a fixed count, the
                default) or PERCENT.
            requires_review: If true, hold the report for human review. The
                job pauses at AWAITING_REVIEW until every finding is decided
                and `confirm_job_report` runs. Defaults to false.
        """
        settings = get_settings()
        params = {
            "database_id": database_id,
            "collection_name": collection_name,
            "condition_types": condition_types,
            "sample_size": sample_size,
            "sample_type": sample_type,
            "requires_review": requires_review,
        }
        response = await classification.create_gdlp_job(params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def update_job_status(job_id: str, status: str) -> dict:
        """Control a running classification job (pause, cancel, or resume).

        Use to manage long-running classification jobs. Status options: PAUSED,
        CANCELLED, or RUNNING.

        Args:
            job_id: Job identifier to update.
            status: New status (PAUSED, CANCELLED, or RUNNING).
        """
        settings = get_settings()
        encoded_id = urllib.parse.quote(job_id, safe='')
        params = {"status": status}
        response = await classification.update_job_status(
            params, settings.auth, encoded_id)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_databricks_job(
            database_id: int,
            collection_name: str | None = None,
            condition_types: list[str] | None = None,
            requires_review: bool | None = None
            ) -> dict:
        """Run a GDLP classification scan on a Databricks database.

        Scans all accessible catalogs and tables in the connected Databricks
        workspace using Google DLP. Runs asynchronously — after creating the
        job, use `get_jobs` to poll for completion, then
        `get_classification_report` to view results.

        Args:
            database_id: ALTR database ID for the Databricks connection
                (from `get_databases` / `get_database_id`).
            collection_name: Optional ALTR collection whose classifiers scope
                this scan. Not limited to GDLP collections — every classifier
                in the collection is evaluated (GDLP info-type conditions or
                otherwise), subject to the condition_types evaluation matrix.
                When omitted, all default Google DLP infoTypes are used.
            condition_types: Optional full set of condition targets to
                evaluate. A list replaces the server default (GDLP, METADATA,
                COLUMN_LOCATION, CONTENT_TYPE; ROW_DATA is left out because
                Databricks GDLP does not evaluate classifier regex against
                samples by default) rather than adding to it, so include GDLP
                if you still want it. Valid values: ROW_DATA, METADATA,
                COLUMN_LOCATION, GDLP, SNOWFLAKE_NATIVE, CONTENT_TYPE,
                DATA_LENGTH, COLUMN_SIZE, AMAZON_COMPREHEND, ENTROPY.
            requires_review: If true, hold the report for human review. The
                job pauses at AWAITING_REVIEW until every finding is decided
                and `confirm_job_report` runs. Defaults to false.
        """
        settings = get_settings()
        params = {
            "database_id": database_id,
            "collection_name": collection_name,
            "condition_types": condition_types,
            "requires_review": requires_review,
        }
        response = await classification.create_databricks_job(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def create_oltp_job(
            agent_id: str,
            repo_name: str,
            service_user_name: str,
            collection_name: str,
            classification_type: int = 5,
            sample_strategy: str = "ROWS",
            sample_size: int | None = None,
            sample_type: str = "ROWS",
            condition_types: list[str] | None = None,
            sid: str | None = None,
            service_name: str | None = None,
            task_id: str | None = None,
            requires_review: bool | None = None
            ) -> dict:
        """Run an on-demand classification scan on an OLTP database
        (Oracle, MSSQL, MySQL, PostgreSQL) via a sidecar classification agent.

        Use this for OLTP/sidecar repos. `create_job` is Snowflake-only — it
        requires a numeric `database_id`, which OLTP repos do not have. This
        triggers an immediate one-off run and does NOT create a scheduled task.

        Runs asynchronously — poll with `get_jobs`, then fetch results with
        `get_job_findings` or `get_classification_report`.

        Args:
            agent_id: CLASSIFIER agent UUID (from `list_sc_agents` with
                agent_type="CLASSIFIER").
            repo_name: Target sidecar repository name (from `list_sc_repos`).
            service_user_name: Repo service user the agent authenticates as
                (from `list_sc_service_users`).
            collection_name: Classifier collection to run.
            classification_type: ALTR classification type code (default 5=ALTR
                Native). Valid values: 5=ALTR Native, 6=GDLP BYOK.
            sample_strategy: Sampling strategy: ROWS (sampled row data),
                METADATA (column names only) or COMBINED (both). Default ROWS;
                GDLP BYOK supports ROWS only.
            sample_size: Rows sampled per column (default 1000), or a
                percentage from 1 to 100 when sample_type is PERCENT, where it
                is required. Not sent for METADATA, which samples no rows.
            sample_type: Sampling unit: ROWS (a fixed count, default) or
                PERCENT. Not sent for METADATA.
            condition_types: Optional full set of condition targets to
                evaluate. When omitted the server derives it from
                sample_strategy and classification_type; a list replaces that
                default rather than adding to it. AMAZON_COMPREHEND must be
                listed to run; GDLP is included by default only for
                classification_type 6. Valid values: ROW_DATA, METADATA,
                COLUMN_LOCATION, CONTENT_TYPE, DATA_LENGTH, COLUMN_SIZE,
                AMAZON_COMPREHEND, GDLP, ENTROPY. Example:
                ["ROW_DATA", "METADATA"].
            sid: Oracle SID (Oracle repos only).
            service_name: Oracle service name or alternate connection identifier.
            task_id: Link this on-demand run to an existing scheduled task UUID.
            requires_review: If true, hold the report for human review. The
                job pauses at AWAITING_REVIEW until every finding is decided
                and `confirm_job_report` runs. Defaults to false.
        """
        settings = get_settings()
        if sample_strategy == "METADATA":
            # The API rejects sampling fields on a metadata scan.
            sample_size, sample_type = None, None
        elif sample_size is None:
            if sample_type == "PERCENT":
                raise ValueError(
                    "sample_size (1-100) is required when sample_type is PERCENT.")
            sample_size = 1000
        params = {
            "agent_id": agent_id,
            "repo_name": repo_name,
            "service_user_name": service_user_name,
            "collection_name": collection_name,
            "classification_type": classification_type,
            "sample_strategy": sample_strategy,
            "sample_size": sample_size,
            "sample_type": sample_type,
            "condition_types": condition_types,
            "sid": sid,
            "service_name": service_name,
            "task_id": task_id,
            "requires_review": requires_review,
        }
        response = await classification.create_oltp_job(
            params, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── Job findings tree ────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings(
            job_id: str,
            limit: int | None = None,
            page_token: str | None = None,
            classifier_name: str | list[str] | None = None,
            confirmed_status: str | None = None,
            include_column_status_counts: bool | None = None
            ) -> dict:
        """List databases found in a completed classification job.

        Entry point for navigating classification results hierarchically
        without downloading the full report. Returns the databases that
        contain detected columns. Drill down with `get_job_findings_schemas`,
        then tables, columns, and classifiers.

        Prefer this over `get_classification_report` when you want to
        interactively explore or filter results by status or classifier.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            limit: Max databases to return.
            page_token: Pagination token from a prior call.
            classifier_name: Filter to databases containing detections by
                these classifier(s). Single string or list.
            confirmed_status: Filter by review status:
                approved, rejected, or pending.
            include_column_status_counts: If true, include approved/
                rejected/pending counts per database.
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if classifier_name:
            params["classifier_name"] = (
                classifier_name if isinstance(classifier_name, list)
                else [classifier_name]
            )
        if confirmed_status:
            params["confirmed_status"] = confirmed_status
        if include_column_status_counts is not None:
            params["include_column_status_counts"] = include_column_status_counts
        response = await classification.get_job_findings(
            job_id, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_schemas(
            job_id: str,
            database: str,
            limit: int | None = None,
            page_token: str | None = None,
            classifier_name: str | list[str] | None = None,
            confirmed_status: str | None = None
            ) -> dict:
        """List schemas in a database from a classification job's findings.

        Second level of the findings tree. Call after `get_job_findings`
        to drill into a specific database.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            database: Database name from `get_job_findings`.
            limit: Max schemas to return.
            page_token: Pagination token.
            classifier_name: Filter by classifier name(s).
            confirmed_status: Filter by review status (approved/rejected/pending).
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if classifier_name:
            params["classifier_name"] = (
                classifier_name if isinstance(classifier_name, list)
                else [classifier_name]
            )
        if confirmed_status:
            params["confirmed_status"] = confirmed_status
        response = await classification.get_job_findings_schemas(
            job_id, database, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_tables(
            job_id: str,
            database: str,
            schema: str,
            limit: int | None = None,
            page_token: str | None = None,
            classifier_name: str | list[str] | None = None,
            confirmed_status: str | None = None
            ) -> dict:
        """List tables in a schema from a classification job's findings.

        Third level of the findings tree.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            database: Database name.
            schema: Schema name from `get_job_findings_schemas`.
            limit: Max tables to return.
            page_token: Pagination token.
            classifier_name: Filter by classifier name(s).
            confirmed_status: Filter by review status (approved/rejected/pending).
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if classifier_name:
            params["classifier_name"] = (
                classifier_name if isinstance(classifier_name, list)
                else [classifier_name]
            )
        if confirmed_status:
            params["confirmed_status"] = confirmed_status
        response = await classification.get_job_findings_tables(
            job_id, database, schema, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_columns(
            job_id: str,
            database: str,
            schema: str,
            table: str,
            limit: int | None = None,
            page_token: str | None = None,
            classifier_name: str | list[str] | None = None,
            confirmed_status: str | None = None
            ) -> dict:
        """List columns in a table from a classification job's findings.

        Fourth level of the findings tree.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            database: Database name.
            schema: Schema name.
            table: Table name from `get_job_findings_tables`.
            limit: Max columns to return.
            page_token: Pagination token.
            classifier_name: Filter by classifier name(s).
            confirmed_status: Filter by review status (approved/rejected/pending).
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if classifier_name:
            params["classifier_name"] = (
                classifier_name if isinstance(classifier_name, list)
                else [classifier_name]
            )
        if confirmed_status:
            params["confirmed_status"] = confirmed_status
        response = await classification.get_job_findings_columns(
            job_id, database, schema, table, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_classifiers(
            job_id: str,
            database: str,
            schema: str,
            table: str,
            column: str,
            limit: int | None = None,
            page_token: str | None = None,
            confirmed_status: str | None = None
            ) -> dict:
        """List classifiers that fired on a specific column in a completed job.

        Fifth (leaf) level of the findings tree. Shows per-classifier detection
        results for a column with confidence scores. Use `get_job_findings_lineage`
        to see the full compound-ruleset evaluation trace for a specific classifier.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            database: Database name.
            schema: Schema name.
            table: Table name.
            column: Column name from `get_job_findings_columns`.
            limit: Max classifiers to return.
            page_token: Pagination token.
            confirmed_status: Filter by review status (approved/rejected/pending).
        """
        settings = get_settings()
        params = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if confirmed_status:
            params["confirmed_status"] = confirmed_status
        response = await classification.get_job_findings_classifiers(
            job_id, database, schema, table, column, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_lineage(
            job_id: str,
            database: str,
            schema: str,
            table: str,
            column: str,
            classifier_name: str
            ) -> dict:
        """Get the compound-ruleset evaluation trace (lineage) for a classifier
        on a specific column in a completed job.

        Returns the full decision tree showing which conditions evaluated,
        which matched, and why the classifier did or did not fire. Useful for
        debugging custom classifiers or understanding AMAZON_COMPREHEND /
        METADATA condition results.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            database: Database name.
            schema: Schema name.
            table: Table name.
            column: Column name.
            classifier_name: Classifier name to inspect.
        """
        settings = get_settings()
        response = await classification.get_job_findings_lineage(
            job_id, database, schema, table, column,
            classifier_name, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_findings_leaves(
            job_id: str,
            limit: int | None = None,
            page_token: str | None = None,
            confidence: list[str] | None = None
            ) -> dict:
        """List every finding in a job in one stream, ordered by full path.

        One row per (database, schema, table, column, classifier), with
        total_findings, match_rate_avg, is_new and the resolved review
        status. Use this to see a whole job at once instead of walking the
        tree with `get_job_findings` and its drill-down tools. Rows are under
        `items`. File sources also return crawl records, with an empty
        classifier_name and no confirmed_status; they are not findings and
        need no decision, and a confidence filter leaves them out.

        Args:
            job_id: Job identifier.
            limit: Max rows per page (default 100, max 1000).
            page_token: next_page_token from a prior call.
            confidence: Keep only these confidence tiers: HIGH, MEDIUM, LOW.
        """
        settings = get_settings()
        params: dict = {}
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        if confidence:
            params["confidence"] = confidence
        response = await classification.get_job_findings_leaves(
            job_id, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── Job decisions ─────────────────────────────────────────────────────────

    @mcp.tool()
    @log_tool
    async def record_job_decision(
            job_id: str,
            confirmed_status: str,
            database: str | None = None,
            schema: str | None = None,
            table: str | None = None,
            column: str | None = None,
            classifier_name: str | None = None
            ) -> dict:
        """Approve or reject classification findings in a job.

        Decisions can be scoped from the entire job down to a specific
        classifier on a specific column. Broader scopes (e.g., entire table)
        apply to all columns and classifiers within that scope.

        After recording decisions, check overall progress with
        `get_job_review_status`. For a job created with requires_review=true,
        finish with `confirm_job_report` to release the report. To decide
        many findings at once, use `record_bulk_job_decision`.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
            confirmed_status: Decision to record: "approved" or "rejected".
            database: Scope to this database (omit for job-wide).
            schema: Scope to this schema (requires database).
            table: Scope to this table (requires schema).
            column: Scope to this column (requires table).
            classifier_name: Scope to this classifier on the column
                (requires column).
        """
        settings = get_settings()
        data: dict = {"confirmed_status": confirmed_status}
        if database is not None:
            data["database"] = database
        if schema is not None:
            data["schema"] = schema
        if table is not None:
            data["table"] = table
        if column is not None:
            data["column"] = column
        if classifier_name is not None:
            data["classifier_name"] = classifier_name
        response = await classification.create_job_decision(
            job_id, data, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_decisions(
            job_id: str,
            database: str | None = None,
            schema: str | None = None,
            table: str | None = None,
            column: str | None = None,
            limit: int | None = None,
            page_token: str | None = None
            ) -> dict:
        """List human review decisions recorded for a classification job.

        Args:
            job_id: Job identifier.
            database: Filter to this database.
            schema: Filter to this schema.
            table: Filter to this table.
            column: Filter to this column.
            limit: Max decisions to return.
            page_token: Pagination token.
        """
        settings = get_settings()
        params: dict = {}
        if database is not None:
            params["database"] = database
        if schema is not None:
            params["schema"] = schema
        if table is not None:
            params["table"] = table
        if column is not None:
            params["column"] = column
        if limit is not None:
            params["limit"] = limit
        if page_token:
            params["page_token"] = page_token
        response = await classification.get_job_decisions(
            job_id, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    @log_tool
    async def revoke_job_decisions(
            job_id: str,
            database: str | None = None,
            schema: str | None = None,
            table: str | None = None,
            column: str | None = None,
            classifier_name: str | None = None
            ) -> dict:
        """Revoke (remove) previously recorded review decisions for a job.

        Scope works the same as `record_job_decision` — revoke at any
        granularity from the whole job down to a single classifier on a column.
        After revoking, those findings return to "pending" status.

        Args:
            job_id: Job identifier.
            database: Scope to this database.
            schema: Scope to this schema.
            table: Scope to this table.
            column: Scope to this column.
            classifier_name: Scope to this classifier.
        """
        settings = get_settings()
        params: dict = {}
        if database is not None:
            params["database"] = database
        if schema is not None:
            params["schema"] = schema
        if table is not None:
            params["table"] = table
        if column is not None:
            params["column"] = column
        if classifier_name is not None:
            params["classifier_name"] = classifier_name
        response = await classification.delete_job_decisions(
            job_id, params, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def record_bulk_job_decision(
            job_id: str,
            confirmed_status: str,
            classifier_names: list[str],
            confidence: list[str] | None = None,
            database: str | None = None,
            schema: str | None = None,
            table: str | None = None,
            dry_run: bool = False
            ) -> dict:
        """Approve or reject every undecided finding that matches a filter.

        Covers findings of the given classifiers, optionally narrowed by
        confidence tier and by a database, schema and table path. Findings
        that already have a decision are left alone, and each covered
        finding can still be overridden with `record_job_decision`. Run with
        dry_run=True first to see how many findings it would cover.

        Returns matched_findings and matched_objects, plus a bulk_decision_id
        when something was recorded (not on a dry run or when nothing
        matched). Undo the whole decision with `revoke_bulk_job_decision`.

        Args:
            job_id: Job identifier.
            confirmed_status: Decision to record: "approved" or "rejected".
            classifier_names: Classifiers whose findings to decide.
            confidence: Keep only these confidence tiers: HIGH, MEDIUM, LOW.
            database: Limit to this database.
            schema: Limit to this schema (requires database).
            table: Limit to this table (requires schema).
            dry_run: If true, return the counts without recording anything.
        """
        if not classifier_names:
            # The engine reads an empty list as every classifier.
            raise ValueError("classifier_names must name at least one classifier.")
        settings = get_settings()
        predicate: dict = {"classifier_names": classifier_names}
        if confidence:
            predicate["confidence"] = confidence
        if database is not None:
            predicate["database"] = database
        if schema is not None:
            predicate["schema"] = schema
        if table is not None:
            predicate["table"] = table
        data = {
            "confirmed_status": confirmed_status,
            "predicate": predicate,
            "dry_run": dry_run,
        }
        response = await classification.create_bulk_job_decision(
            job_id, data, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    @log_tool
    async def revoke_bulk_job_decision(
            job_id: str, bulk_decision_id: str) -> dict:
        """Undo a bulk decision recorded with `record_bulk_job_decision`.

        Revokes every decision it still covers. A finding decided
        individually afterwards keeps that individual decision.

        Args:
            job_id: Job identifier.
            bulk_decision_id: bulk_decision_id returned by
                `record_bulk_job_decision`.
        """
        settings = get_settings()
        response = await classification.delete_bulk_job_decision(
            job_id, bulk_decision_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_job_review_status(job_id: str) -> dict:
        """Get the review progress for a classification job.

        Returns total/approved/rejected/pending counts across all findings.
        Use after recording decisions with `record_job_decision` to check
        how much review work remains.

        Args:
            job_id: Identifier of a COMPLETED job, or of a review-gated job at
                AWAITING_REVIEW.
        """
        settings = get_settings()
        response = await classification.get_job_review_status(
            job_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    # ── Report ───────────────────────────────────────────────────────────────

    @mcp.tool()
    @log_tool
    async def confirm_job_report(job_id: str) -> dict:
        """Confirm the review of a review-gated job and release its report.

        For a job created with requires_review=true. Every finding must have
        a decision; check with `get_job_review_status` first. Generation
        then runs in the background and decisions are locked: poll `get_job`
        until the status is COMPLETED, then read the report with
        `get_classification_report`.

        Args:
            job_id: Job identifier.
        """
        settings = get_settings()
        response = await classification.confirm_job_report(
            job_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool()
    @log_tool
    async def cancel_job_report(job_id: str) -> dict:
        """Cancel a review-gated job before its report is confirmed.

        For a job created with requires_review=true that is still being
        reviewed. The job moves to CANCELLED and its review data is
        discarded. A job whose report has already been confirmed cannot be
        cancelled this way.

        Args:
            job_id: Job identifier.
        """
        settings = get_settings()
        response = await classification.cancel_job_report(
            job_id, settings.auth)
        return {"success": True, "data": response, "error": None}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    @log_tool
    async def get_classification_report(job_id: str) -> dict:
        """Get detailed results from a completed classification job.

        Returns which columns were detected as containing
        sensitive data along with confidence scores. Only call
        after the job status is COMPLETED (verify with
        `get_jobs`).

        For interactive navigation, prefer `get_job_findings` which
        lets you drill down without downloading the full report.

        After reviewing results, check if the needed Snowflake
        tags exist using `get_tags`. If tags are missing, they
        must be created in Snowflake first before connecting
        with `connect_tag`.

        Args:
            job_id: Job identifier returned from `create_job`
                or listed by `get_jobs`.
        """
        settings = get_settings()
        params = {}
        response = await classification.get_job_report(
            params, settings.auth, job_id)
        return {"success": True, "data": response, "error": None}
