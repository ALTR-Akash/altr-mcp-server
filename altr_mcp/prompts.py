"""Troubleshooting prompts served by the server.

Shipping these as MCP prompts rather than as text on a wiki page fixes
three things at once. The customer picks one from a menu instead of
pasting it, so there is nothing to paste wrongly. The guardrail line
cannot be edited out on the way, because it is not transcribed. And the
wording versions with the server, so improving a prompt does not mean
re-sending anything to anyone.

Every prompt opens by telling the model to call `enter_support_mode`.
That is what makes read-only real for a customer who was never going to
set an environment variable: enforcement lands in middleware, so a
later "just change it for me" fails there rather than depending on the
model still remembering an instruction from ten turns ago.
"""

from fastmcp import FastMCP

_ARM = (
    "First, call the `enter_support_mode` tool. Do not skip this and do"
    " not call any other tool before it. It withholds every write tool"
    " for the rest of this session, and it needs no restart or config"
    " change. If it returns an error, stop and tell me what it said"
    " rather than continuing unprotected.\n\n"
    "Then investigate, read-only, and report findings. If fixing this"
    " needs a change, name the tool and what it would change, and ask"
    " me before doing anything. Do not leave support mode to make a"
    " change.\n\n"
)


def register(mcp: FastMCP) -> None:

    @mcp.prompt(
        name="altr_masking_not_applying",
        description=(
            "A Snowflake column returns raw values where you expected"
            " masking. Reports why the mask is not landing."
        ),
    )
    def masking_not_applying(
        column: str = "<DB>.<SCHEMA>.<TABLE>.<COLUMN>",
        role: str = "<ROLE>",
    ) -> str:
        return (
            f"{_ARM}"
            f"My Snowflake column {column} is still returning raw values"
            f" for role {role}, but I expected it to be masked. Check:"
            " which tags are connected, whether any tag covers this"
            " column, which masking policies exist and their rules, what"
            f" masking level applies to {role}, and whether that role is"
            " even known to ALTR. Tell me the specific reason it is not"
            " masking, and list what is missing."
        )

    @mcp.prompt(
        name="altr_masking_returns_null",
        description=(
            "Queries return NULL or an error where masked values were"
            " expected. Usually a masking level that does not fit the"
            " column type."
        ),
    )
    def masking_returns_null(
        table: str = "<DB>.<SCHEMA>.<TABLE>",
        role: str = "<ROLE>",
    ) -> str:
        return (
            f"{_ARM}"
            f"Queries against {table} are returning NULL or an error"
            f" where I expected masked values, for role {role}. Check the"
            " policies and rules that apply, and specifically look for a"
            " masking level that does not fit the column's data type."
            " Report the policy, the rule, the masking level, and whether"
            " the level is compatible with the column type."
        )

    @mcp.prompt(
        name="altr_classification_job_stuck",
        description=(
            "A classification job looks stuck. Reports whether it is"
            " actually running, and whether its runtime is normal."
        ),
    )
    def classification_job_stuck(
        database: str = "<DB>",
        started: str = "<TIME>",
    ) -> str:
        return (
            f"{_ARM}"
            f"I started an ALTR classification job on {database} around"
            f" {started}. List my recent jobs with status and timestamps,"
            " and tell me whether it is still running, completed, or"
            " failed. Do not start a new job, even if I ask, without"
            " telling me first that the existing one is still running."
            " If it is still running, tell me how long it has been going"
            " and whether that is within normal range."
        )

    @mcp.prompt(
        name="altr_classification_results_wrong",
        description=(
            "A finished classification job produced wrong or incomplete"
            " findings. Walks the findings to column level."
        ),
    )
    def classification_results_wrong(
        job_id: str = "<JOB_ID>",
        database: str = "<DB>",
        table: str = "<SCHEMA>.<TABLE>",
    ) -> str:
        return (
            f"{_ARM}"
            f"My classification job {job_id} on {database} finished, but"
            " the results look wrong. Pull the job summary and walk the"
            f" findings down to the column level for {table}. Tell me"
            " which classifiers fired, which columns were flagged, and"
            " which findings are still pending review versus approved or"
            " rejected. Do not approve, reject, or change any finding."
        )

    @mcp.prompt(
        name="altr_sidecar_not_connecting",
        description=(
            "A sidecar will not show as connected. Reports the whole"
            " object tree and which piece is missing."
        ),
    )
    def sidecar_not_connecting(sidecar: str = "<SIDECAR_NAME>") -> str:
        return (
            f"{_ARM}"
            f"My ALTR sidecar {sidecar} is not showing as connected."
            " Report: the sidecar's configuration, its registered"
            " listeners, its instances and their last-seen status, and"
            " the repos and bindings attached to it. Then tell me which"
            " piece is missing or misconfigured."
        )

    @mcp.prompt(
        name="altr_sidecar_impersonation_failing",
        description=(
            "Cannot connect through the sidecar as a database user."
            " Checks the impersonation chain and the repo name mismatch."
        ),
    )
    def sidecar_impersonation_failing(
        repo: str = "<REPO_NAME>",
        db_user: str = "<DB_USER>",
        my_email: str = "<MY_EMAIL>",
    ) -> str:
        return (
            f"{_ARM}"
            f"I cannot connect to repo {repo} through the sidecar as user"
            f" {db_user}. Check the repo config, the repo users defined in"
            " ALTR, the sidecar bindings, and any impersonation policies"
            f" that should let {my_email} impersonate {db_user}. Report"
            " exactly which link in that chain is missing. Also flag any"
            " mismatch between the repo name in the connection string and"
            " the repo name registered in ALTR, including hyphens versus"
            " underscores."
        )

    @mcp.prompt(
        name="altr_cannot_disconnect_resource",
        description=(
            "ALTR refuses to disconnect something. Enumerates what is"
            " still attached, in teardown order."
        ),
    )
    def cannot_disconnect_resource(resource: str = "<RESOURCE>") -> str:
        return (
            f"{_ARM}"
            f"ALTR will not let me disconnect {resource}. Enumerate"
            " everything still attached to it, in teardown order:"
            " bindings, then users, then listeners, then the sidecar,"
            " then the repo. For a Snowflake database, also check"
            " connected tags and policies. Give me the exact ordered list"
            " of what I need to remove first.\n\n"
            "Do not remove anything and do not retry the disconnect. Send"
            " me the list so I can confirm it with ALTR support before"
            " anything is removed, because removing these in the wrong"
            " order can take a live database proxy offline.\n\n"
            "If you find no tags and no policies and the disconnect still"
            " fails, say so explicitly: the blocker is then column-level"
            " governance, which no tool here can list, and it has to be"
            " cleared in the ALTR portal under Data Sources."
        )

    @mcp.prompt(
        name="altr_who_accessed_data",
        description=(
            "Who queried a table in a time window, and what masking they"
            " received. Reports masking levels, never values."
        ),
    )
    def who_accessed_data(
        table: str = "<DB>.<SCHEMA>.<TABLE>",
        start: str = "<START>",
        end: str = "<END>",
    ) -> str:
        return (
            f"{_ARM}"
            f"I need to know who queried {table} between {start} and"
            f" {end}, and what masking they received. Search the query"
            " audits and summarize by user and role. Report the masking"
            " level applied, not the underlying values. Quote only the"
            " query text you need, since audit query text routinely"
            " contains literal customer values."
        )
