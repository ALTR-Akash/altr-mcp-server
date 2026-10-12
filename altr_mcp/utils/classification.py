from altr_mcp.utils import api
from altr_mcp.settings import get_settings
import urllib.parse


async def _paginate_altr_request(
        url: str,
        params: dict,
        auth,
        resource_type: str
        ) -> dict:
    method = "GET"
    last_evaluated_key = {}
    response = {"data": {resource_type: []}}
    while last_evaluated_key is not None:
        temp_response = await api.request(method, url, auth, params)
        contiguous_id = temp_response.get("contiguous_id", None)
        if contiguous_id is not None:
            params["contiguous_id"] = contiguous_id
        else:
            last_evaluated_key = None
        response["data"][resource_type] += temp_response.get(resource_type, [])
    return response


# --- Classifiers ---

async def get_classifiers(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/classifiers"
    return await _paginate_altr_request(url, params, auth, "classifiers")


async def get_classifier(name: str, auth) -> dict:
    encoded_name = urllib.parse.quote(name, safe='')
    url = f"{get_settings().classification_base_url}/v1/classifiers/{encoded_name}"
    return await api.request("GET", url, auth, {})


async def create_classifier(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/classifiers"
    data = {
        "classifier_name": params.get("classifier_name"),
        "description": params.get("description"),
        "minimum_threshold": params.get("minimum_threshold"),
        "pattern": params.get("pattern"),
        "sample_size": params.get("sample_size"),
    }
    if params.get("compound_ruleset") is not None:
        data["compound_ruleset"] = params["compound_ruleset"]
    data = {k: v for k, v in data.items() if v is not None}
    return await api.request("POST", url, auth, {}, data)


async def update_classifier(name: str, params: dict, auth) -> dict:
    encoded_name = urllib.parse.quote(name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/classifiers/{encoded_name}"
    )
    return await api.request("PATCH", url, auth, {}, params)


async def delete_classifier(params: dict, auth) -> dict:
    classifier_name = params.get("classifier_name")
    encoded_name = urllib.parse.quote(classifier_name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/classifiers/{encoded_name}"
    )
    return await api.request("DELETE", url, auth, {})


# --- Collections ---

async def get_collections(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/collections"
    return await _paginate_altr_request(url, params, auth, "collections")


async def get_collection(name: str, auth) -> dict:
    encoded_name = urllib.parse.quote(name, safe='')
    url = f"{get_settings().classification_base_url}/v1/collections/{encoded_name}"
    return await api.request("GET", url, auth, {})


async def create_collection(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/collections"
    data = {
        "collection_name": params.get("collection_name"),
        "description": params.get("description", ""),
    }
    return await api.request("POST", url, auth, {}, data)


async def update_collection(name: str, params: dict, auth) -> dict:
    encoded_name = urllib.parse.quote(name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/collections/{encoded_name}"
    )
    return await api.request("PATCH", url, auth, {}, params)


async def delete_collection(params: dict, auth) -> dict:
    collection_name = params.get("collection_name")
    encoded_name = urllib.parse.quote(collection_name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/collections/{encoded_name}"
    )
    return await api.request("DELETE", url, auth, {})


async def get_collection_classifiers(name: str, params: dict, auth) -> dict:
    encoded_name = urllib.parse.quote(name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/collections/{encoded_name}/classifiers"
    )
    return await api.request("GET", url, auth, params)


async def append_classifiers_to_collection(
        collection_name: str, classifier_names: list, auth) -> dict:
    encoded_name = urllib.parse.quote(collection_name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/collections/{encoded_name}/classifiers/append"
    )
    data = {"classifier_names": classifier_names}
    return await api.request("PATCH", url, auth, {}, data=data)


async def remove_classifiers_from_collection(
        collection_name: str, classifier_names: list, auth) -> dict:
    encoded_name = urllib.parse.quote(collection_name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/collections/{encoded_name}/classifiers/remove"
    )
    data = {"classifier_names": classifier_names}
    return await api.request("PATCH", url, auth, {}, data=data)


# --- ALTR-managed collections ---

async def import_altr_managed_classifiers(auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/collections/altr-managed/import"
    return await api.request("POST", url, auth, {}, {})


async def get_altr_managed_timestamp(auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/collections/altr-managed/timestamp"
    return await api.request("GET", url, auth, {})


async def list_altr_managed_classifiers(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/collections/altr-managed/classifiers"
    return await api.request("GET", url, auth, params)


# --- Jobs ---

async def get_jobs(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs"
    return await _paginate_altr_request(url, params, auth, "jobs")


async def get_active_jobs(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/active"
    return await api.request("GET", url, auth, params)


async def get_job(job_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}"
    return await api.request("GET", url, auth, {})


async def get_job_summary(job_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}/summary"
    return await api.request("GET", url, auth, {})


async def update_job_status(params: dict, auth, job_id: str) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/{job_id}"
    data = {"status": params.get("status")}
    return await api.request("PATCH", url, auth, {}, data)


async def create_job(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/snowflake"
    data = {
        "job_type": params.get("job_type"),
        "database_id": params.get("database_id"),
        "collection_name": params.get("collection_name"),
        "classification_type": "altr_native",
    }
    if params.get("condition_types"):
        data["condition_types"] = params["condition_types"]
    if params.get("requires_review") is not None:
        data["requires_review"] = params["requires_review"]
    return await api.request("POST", url, auth, {}, data)


async def create_gdlp_job(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/snowflake"
    data = {
        "database_id": params.get("database_id"),
        "classification_type": "gdlp",
    }
    if params.get("collection_name"):
        data["collection_name"] = params["collection_name"]
    if params.get("condition_types"):
        data["condition_types"] = params["condition_types"]
    if params.get("sample_size") is not None:
        data["sample_size"] = params["sample_size"]
    if params.get("sample_type"):
        data["sample_type"] = params["sample_type"]
    if params.get("requires_review") is not None:
        data["requires_review"] = params["requires_review"]
    return await api.request("POST", url, auth, {}, data)


async def create_databricks_job(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/databricks"
    data = {"database_id": params.get("database_id")}
    if params.get("collection_name"):
        data["collection_name"] = params["collection_name"]
    if params.get("condition_types"):
        data["condition_types"] = params["condition_types"]
    if params.get("requires_review") is not None:
        data["requires_review"] = params["requires_review"]
    return await api.request("POST", url, auth, {}, data)


async def create_oltp_job(params: dict, auth) -> dict:
    url = f"{get_settings().classification_base_url}/v1/jobs/oltp"
    data = {
        "agent_id": params.get("agent_id"),
        "repo_name": params.get("repo_name"),
        "service_user_name": params.get("service_user_name"),
        "collection_name": params.get("collection_name"),
        "classification_type": params.get("classification_type"),
        "sample_strategy": params.get("sample_strategy"),
        "sample_size": params.get("sample_size"),
        "sample_type": params.get("sample_type"),
        "condition_types": params.get("condition_types"),
        "sid": params.get("sid"),
        "service_name": params.get("service_name"),
        "task_id": params.get("task_id"),
        "requires_review": params.get("requires_review"),
    }
    data = {k: v for k, v in data.items() if v is not None}
    return await api.request("POST", url, auth, {}, data)


# --- Job findings (tree navigation) ---

async def get_job_findings(job_id: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}/findings"
    return await api.request("GET", url, auth, params)


async def get_job_findings_leaves(job_id: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/leaves"
    )
    return await api.request("GET", url, auth, params)


async def get_job_findings_schemas(
        job_id: str, database: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_db = urllib.parse.quote(database, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/databases/{encoded_db}/schemas"
    )
    return await api.request("GET", url, auth, params)


async def get_job_findings_tables(
        job_id: str, database: str, schema: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_db = urllib.parse.quote(database, safe='')
    encoded_schema = urllib.parse.quote(schema, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/databases/{encoded_db}"
        f"/schemas/{encoded_schema}/tables"
    )
    return await api.request("GET", url, auth, params)


async def get_job_findings_columns(
        job_id: str, database: str, schema: str, table: str,
        params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_db = urllib.parse.quote(database, safe='')
    encoded_schema = urllib.parse.quote(schema, safe='')
    encoded_table = urllib.parse.quote(table, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/databases/{encoded_db}"
        f"/schemas/{encoded_schema}/tables/{encoded_table}/columns"
    )
    return await api.request("GET", url, auth, params)


async def get_job_findings_classifiers(
        job_id: str, database: str, schema: str, table: str, column: str,
        params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_db = urllib.parse.quote(database, safe='')
    encoded_schema = urllib.parse.quote(schema, safe='')
    encoded_table = urllib.parse.quote(table, safe='')
    encoded_col = urllib.parse.quote(column, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/databases/{encoded_db}"
        f"/schemas/{encoded_schema}/tables/{encoded_table}"
        f"/columns/{encoded_col}/classifiers"
    )
    return await api.request("GET", url, auth, params)


async def get_job_findings_lineage(
        job_id: str, database: str, schema: str, table: str, column: str,
        classifier_name: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_db = urllib.parse.quote(database, safe='')
    encoded_schema = urllib.parse.quote(schema, safe='')
    encoded_table = urllib.parse.quote(table, safe='')
    encoded_col = urllib.parse.quote(column, safe='')
    encoded_clf = urllib.parse.quote(classifier_name, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/findings/databases/{encoded_db}"
        f"/schemas/{encoded_schema}/tables/{encoded_table}"
        f"/columns/{encoded_col}/classifiers/{encoded_clf}/lineage"
    )
    return await api.request("GET", url, auth, {})


# --- Job decisions ---

async def create_job_decision(job_id: str, data: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}/decisions"
    return await api.request("POST", url, auth, {}, data)


async def get_job_decisions(job_id: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}/decisions"
    return await api.request("GET", url, auth, params)


async def delete_job_decisions(job_id: str, params: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = f"{get_settings().classification_base_url}/v1/jobs/{encoded_id}/decisions"
    return await api.request("DELETE", url, auth, params)


async def create_bulk_job_decision(job_id: str, data: dict, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/decisions/bulk"
    )
    return await api.request("POST", url, auth, {}, data)


async def delete_bulk_job_decision(
        job_id: str, bulk_decision_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    encoded_bulk_id = urllib.parse.quote(bulk_decision_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/decisions/bulk/{encoded_bulk_id}"
    )
    return await api.request("DELETE", url, auth, {})


async def get_job_review_status(job_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/review-status"
    )
    return await api.request("GET", url, auth, {})


# --- Job report ---

async def confirm_job_report(job_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/report/confirm"
    )
    return await api.request("POST", url, auth, {})


async def cancel_job_report(job_id: str, auth) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/report/cancel"
    )
    return await api.request("POST", url, auth, {})


async def _create_job_report(params: dict, auth, job_id: str) -> dict:
    encoded_id = urllib.parse.quote(job_id, safe='')
    url = (
        f"{get_settings().classification_base_url}"
        f"/v1/jobs/{encoded_id}/report"
    )
    return await api.request("POST", url, auth, params, {})


async def get_job_report(params: dict, auth, job_id: str) -> dict:
    job_url = await _create_job_report(params, auth, job_id)
    url = job_url.get("url")
    if not url:
        # Creation failed -- a bad job id, a 4xx, retries exhausted.
        # api.request has already shaped that into {success, status_code,
        # message}, so pass it through rather than indexing ["url"] and
        # turning the real cause into KeyError: 'url'.
        return job_url
    # A presigned download URL, so no ALTR auth is attached. Goes through
    # the shared client for connection reuse and to pick up the configured
    # timeout -- httpx's own default is 5s, short for a report download.
    resp = await api.get_client().get(
        url, timeout=get_settings().request_timeout)
    if resp.status_code >= 400:
        # Presigned URLs expire -- _create_job_report returns an expiration
        # alongside the URL -- and S3 answers an expired one with a 403 and
        # an XML body, so resp.json() would raise a JSONDecodeError and bury
        # the actual cause.
        return {
            "success": False,
            "status_code": resp.status_code,
            "message": f"Report download failed (HTTP {resp.status_code})",
        }
    return resp.json()
