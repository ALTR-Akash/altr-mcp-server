from fastmcp import FastMCP


def register_all(mcp: FastMCP) -> None:
    """Register all tool handlers with the MCP server.

    Imports are deferred to avoid circular dependencies with server.py.
    """
    from altr_mcp.tools import (
        access_management,
        access_request,
        audit,
        audit_report,
        classification,
        critical_tokenization,
        dam_alerting,
        database,
        key_management,
        policy,
        sidecar_config,
        tag,
        telemetry,
        vault_tokenization,
    )

    policy.register(mcp)
    tag.register(mcp)
    classification.register(mcp)
    database.register(mcp)
    access_management.register(mcp)
    access_request.register(mcp)
    telemetry.register(mcp)
    audit.register(mcp)
    audit_report.register(mcp)
    dam_alerting.register(mcp)
    sidecar_config.register(mcp)
    vault_tokenization.register(mcp)
    critical_tokenization.register(mcp)
    key_management.register(mcp)
