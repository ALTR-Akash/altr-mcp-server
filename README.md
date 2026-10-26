# ALTR MCP Server

<!-- mcp-name: io.github.altrsoftware/altr-mcp-server -->

[![PyPI](https://img.shields.io/pypi/v/altr-mcp.svg)](https://pypi.org/project/altr-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/altr-mcp)](https://pypi.org/project/altr-mcp/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.md)
[![CI](https://github.com/altrsoftware/altr-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/altrsoftware/altr-mcp-server/actions/workflows/ci.yml)
[![Security](https://github.com/altrsoftware/altr-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/altrsoftware/altr-mcp-server/actions/workflows/security.yml)

[ALTR](https://www.altr.com) provides tag-based data masking, access governance, and classification for Snowflake, Databricks, and OLTP databases. This MCP server enables AI assistants (Claude, Cursor, and other MCP clients) to manage data security on the ALTR platform, covering database connections, tag masking, policies, classification, access management, audits, telemetry, and sidecar configuration.

> **New to ALTR?** See the [ALTR documentation](https://docs.altr.com) for an overview of the platform, concepts, and supported data sources.

All tools return structured `{success, data, error}` responses and can run over stdio, SSE, or streamable-http transports.

## Table of Contents

- [Quick Start](#quick-start)
- [Getting Credentials](#getting-credentials)
- [Configuration](#configuration)
  - [Restricting Tools](#restricting-tools)
- [Setup](#setup)
  - [Claude Desktop](#claude-desktop)
  - [Claude Code (CLI)](#claude-code-cli)
  - [Cursor](#cursor)
  - [VS Code (GitHub Copilot)](#vs-code-github-copilot)
  - [Windsurf](#windsurf)
  - [Running from Local Source](#running-from-local-source)
- [CLI](#cli-optional)
- [Tools](#tools)
- [Data Source Support](#data-source-support)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Quick Start

1. **Install from PyPI:**

   ```bash
   pip install altr-mcp
   ```

   Or run directly with [uvx](https://docs.astral.sh/uv/guides/tools/) (no install required):

   ```bash
   uvx altr-mcp
   ```

   > `uvx` is part of the [uv](https://docs.astral.sh/uv/) Python package manager. Install it with `pip install uv` or see the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

2. **Set the three required environment variables** (see [Getting Credentials](#getting-credentials) for where to find each in the ALTR console):

   ```bash
   export ORG_ID=your-org-id
   export MAPI_KEY=your-api-key
   export MAPI_SECRET=your-api-secret
   ```

3. **Wire it into your AI client** — see [Setup](#setup) for Claude Desktop, Claude Code, Cursor, VS Code, and Windsurf. The same three env vars go into the client's `env` block.

4. **Verify** by asking your AI assistant to run a read-only tool:

   - "List my ALTR databases" → calls `get_databases`
   - "Show me the tags connected to ALTR" → calls `get_tags`
   - "List the ALTR roles in my org" → calls `get_roles`

   If these return data, your setup is working.

## Getting Credentials

You need three values from the ALTR platform to configure this server. See [Manage API keys](https://docs.altr.com/account-and-api/api/api-keys/) for the full reference.

| Credential | Where to find it |
|---|---|
| `ORG_ID` | In the ALTR console: **Settings > Preferences > Organization** — copy the value from "ALTR Organization ID" |
| `MAPI_KEY` | In the ALTR console: **Settings > Preferences > API > Add New** — give it a description, then copy the key |
| `MAPI_SECRET` | Shown once when you create the API key above — copy and store it securely |

## Configuration

Set the following environment variables before starting the server:

| Variable | Required | Description |
|---|---|---|
| `ORG_ID` | Yes | ALTR organization ID |
| `MAPI_KEY` | Yes | ALTR management API key |
| `MAPI_SECRET` | Yes | ALTR management API secret |
| `MCP_TRANSPORT` | No | Transport protocol: `stdio` (default), `sse`, or `streamable-http` |
| `MCP_HOST` | No | Bind address for HTTP transports (default: `0.0.0.0`) |
| `MCP_PORT` | No | Port for HTTP transports (default: `8000`) |
| `RESTRICTED_TOOLS` | No | Comma-separated tool names to hide from clients |
| `LOG_FORMAT` | No | Log output format: `console` (default) or `json` |
| `LOG_LEVEL` | No | Log level (default: `INFO`) |
| `MAX_RETRIES` | No | Attempts per API call before giving up (default: `3`, minimum `1`) |
| `DISABLE_RETRY` | No | Set `true` to disable retries entirely (default: `false`) |
| `REQUEST_TIMEOUT` | No | Per-request timeout in seconds (default: `30`) |
| `MAX_RETRY_AFTER` | No | Ceiling in seconds on a server-sent `Retry-After` (default: `60`) |

`MAX_RETRIES` counts total attempts, not retries on top of the first, so `1`
disables retrying without disabling the retry path. Backoff is exponential with
jitter; a `Retry-After` response header overrides it, clamped to
`MAX_RETRY_AFTER` so a server cannot park a call indefinitely.

#### What gets logged

Every tool call is logged to stderr at `INFO` with its arguments, which is what
makes a session traceable. An argument is redacted when its value is a
credential or user-supplied free text — `values`, `text`, `comments`,
`attestation`, `justification`, `statement_text_contains`, `filters`,
`connection_string`, the bare credential names (`password`, `secret`,
`credentials`, `passphrase`, `private_key`, `api_key`, `auth_token`,
`access_key`), and anything ending `_password`, `_secret`, `_credential`,
`_credentials`, `_private_key` or `_passphrase`. Identifiers, enums and
pagination cursors are logged in full.

An argument can also reach a log by travelling in a request URL, which
redaction keyed on argument names cannot see. httpx's per-request line is
therefore held at `WARNING`, so it does not appear at the default `INFO`.

Dictionary keys survive, so a line reads
`values={'ssn': '<redacted>', 'email': '<redacted>'}`: you keep which fields
were sent and lose the data. Tokens are not redacted — a token exists to be
handled freely, and ALTR's own Shield audit log is keyed by token.

Redaction covers the invocation line, tracebacks, and the argument-coercion
error returned to the caller.

`LOG_FORMAT` applies to dependency output as well as this server's own — under
`json`, every line on the stream is a JSON object, and dependency lines carry
the `correlation_id` of the tool call they occurred inside. See
[Logging](./docs/logging.md).

> **Upgrading from 0.6.0 or earlier?** Arguments were not redacted before
> 0.7.0. Treat any credential passed as a tool argument as exposed in your
> logs and rotate it — in practice `database_password` and
> `connection_string`. Those logs may also hold plaintext passed to the
> tokenize tools, so review who can read them and how long they are kept. Log
> output also changed shape; see the 0.7.0 entry in the
> [CHANGELOG](./CHANGELOG.md).

#### Endpoint overrides

Every ALTR service endpoint can be pointed elsewhere, which is useful against
a non-production ALTR environment. All are optional — leave them unset in
normal use.

The eight per-service endpoints are derived from your `ORG_ID` as
`https://<ORG_ID>.<service>.live.altr.com`, five of them with a path appended
(a version, or `/v1/dam-alerting`). An override replaces the whole value, so it
must include that path where the default has one — see the table.

| Variable | Default |
|---|---|
| `ALTR_API_BASE_URL` | `https://api.live.altr.com` |
| `ALTR_ALTRNET_BASE_URL` | `https://altrnet.live.altr.com` |
| `ALTR_CLASSIFICATION_BASE_URL` | `https://<ORG_ID>.classification.live.altr.com` |
| `ALTR_SC_CONTROL_BASE_URL` | `https://<ORG_ID>.sc-control.live.altr.com` |
| `ALTR_SERVICE_USER_BASE_URL` | `https://<ORG_ID>.service-user.live.altr.com` |
| `ALTR_AUDIT_REPORT_BASE_URL` | `https://<ORG_ID>.audit-report.live.altr.com/v1` |
| `ALTR_VAULT_BASE_URL` | `https://<ORG_ID>.vault.live.altr.com/api/v2` |
| `ALTR_CRITICAL_BASE_URL` | `https://<ORG_ID>.critical.live.altr.com/v2` |
| `ALTR_KMA_BASE_URL` | `https://<ORG_ID>.kma.live.altr.com/v1` |
| `ALTR_DAM_ALERTING_BASE_URL` | `https://<ORG_ID>.dam-alerting.live.altr.com/v1/dam-alerting` |

### Restricting Tools

Use `RESTRICTED_TOOLS` to hide specific tools from MCP clients. Restricted tools are removed from the tool list and blocked if called directly.

Names must match the registered tool name exactly. An entry that matches nothing restricts nothing, and is logged as a warning the first time a client lists tools. Note that 11 tools were renamed from `delete_*` to `disconnect_*` in 0.4.0.

For example, to give a team read-only access without any destructive operations:

```bash
RESTRICTED_TOOLS=disconnect_database,delete_policy,delete_rule,disconnect_tag,disconnect_tag_by_details,delete_classifier,delete_collection,disconnect_sc_repo,disconnect_sc_sidecar
```

Or in the Claude Desktop config:

```json
{
  "mcpServers": {
    "altr": {
      "command": "uvx",
      "args": ["altr-mcp"],
      "env": {
        "ORG_ID": "your-org-id",
        "MAPI_KEY": "your-api-key",
        "MAPI_SECRET": "your-api-secret",
        "RESTRICTED_TOOLS": "disconnect_database,delete_policy,delete_rule,disconnect_tag"
      }
    }
  }
}
```

This is an operator-level safety net — it prevents accidental or unwanted tool usage but is not a substitute for proper API key permissions.

## Setup

### Claude Desktop

Add the following to your `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "altr": {
      "command": "uvx",
      "args": ["altr-mcp"],
      "env": {
        "ORG_ID": "your-org-id",
        "MAPI_KEY": "your-api-key",
        "MAPI_SECRET": "your-api-secret"
      }
    }
  }
}
```

### Claude Code (CLI)

```bash
claude mcp add altr -e ORG_ID=your-org-id -e MAPI_KEY=your-api-key -e MAPI_SECRET=your-api-secret -- uvx altr-mcp
```

This writes the config to `.mcp.json` which can be committed to share with your team.

### Cursor

Add to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-scoped):

```json
{
  "mcpServers": {
    "altr": {
      "command": "uvx",
      "args": ["altr-mcp"],
      "env": {
        "ORG_ID": "your-org-id",
        "MAPI_KEY": "your-api-key",
        "MAPI_SECRET": "your-api-secret"
      }
    }
  }
}
```

### VS Code (GitHub Copilot)

Open User Settings JSON (Ctrl+Shift+P → "Preferences: Open User Settings (JSON)") and add:

```json
{
  "mcp": {
    "servers": {
      "altr": {
        "command": "uvx",
        "args": ["altr-mcp"],
        "env": {
          "ORG_ID": "your-org-id",
          "MAPI_KEY": "your-api-key",
          "MAPI_SECRET": "your-api-secret"
        }
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "altr": {
      "command": "uvx",
      "args": ["altr-mcp"],
      "env": {
        "ORG_ID": "your-org-id",
        "MAPI_KEY": "your-api-key",
        "MAPI_SECRET": "your-api-secret"
      }
    }
  }
}
```

### Running from Local Source

To run from a local clone instead of the published PyPI package:

**Claude Code:**

```bash
claude mcp add altr \
  -e ORG_ID=your-org-id \
  -e MAPI_KEY=your-api-key \
  -e MAPI_SECRET=your-api-secret \
  -- uv run --directory /path/to/altr-mcp altr-mcp
```

**Claude Desktop:**

```json
{
  "mcpServers": {
    "altr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/altr-mcp", "altr-mcp"],
      "env": {
        "ORG_ID": "your-org-id",
        "MAPI_KEY": "your-api-key",
        "MAPI_SECRET": "your-api-secret"
      }
    }
  }
}
```

## CLI (Optional)

> This section is for building a standalone CLI binary from the MCP server. If you just want to use the server with Claude Desktop or Claude Code, skip to [Tools](#tools).

A standalone CLI lets you call ALTR tools directly from the terminal without an MCP client. It's built with [mcporter](https://github.com/openclaw/mcporter), an open-source tool that compiles MCP servers into native CLI binaries. See the [mcporter docs](https://github.com/openclaw/mcporter) for the full set of options.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js](https://nodejs.org/) (for `npx` to fetch and run `mcporter`)

`mcporter` itself does not need to be installed separately — `npx` downloads and runs it on demand.

### Building

From the repo root:

```bash
npx mcporter generate-cli --command "uv run --directory . altr-mcp" --name altr-cli --compile ./altr-cli
```

This generates a compiled binary at `./altr-cli`.

### Usage

Set your credentials as environment variables, then run any tool:

```bash
export ORG_ID=your-org-id
export MAPI_KEY=your-api-key
export MAPI_SECRET=your-api-secret

# List databases
./altr-cli get-databases

# Get a specific database ID
./altr-cli get-database-id --database-name "my_database"

# Create a masking policy
./altr-cli create-policy --tag "STOPLIGHT"

# Add rules (pass JSON string for complex params)
./altr-cli add-rules --policy-id "TAG#abc123" --rules '[{"masking_policy": 10001, "role": "PUBLIC", "tag_value": "red"}]'

# Search query audits
./altr-cli search-query-audits --limit 10

# JSON output
./altr-cli get-databases --output json

# See all available commands
./altr-cli --help
```

The CLI runs the MCP server locally via `uv run` and requires the repo to be present at the working directory. All environment variables from the [Configuration](#configuration) section apply.

## Tools

For a full breakdown of every tool with parameters, behavior, and examples, see [docs/index.md](./docs/index.md).

| Domain | Tools | What it does |
|---|---|---|
| [Databases](./docs/databases.md) | 8 | Connect Snowflake, OLTP, and Databricks data sources. Setup per platform: [Snowflake](https://docs.altr.com/data-sources/snowflake/), [OLTP](https://docs.altr.com/data-sources/oltp/), [Databricks](https://docs.altr.com/data-sources/databricks/). |
| [Tags](./docs/tags.md) | 8 | Manage Snowflake tag connections to ALTR. See [Connecting Snowflake Tags to ALTR](https://docs.altr.com/data-sources/snowflake/policy-on-snowflake/manage-tags/). |
| [Policies & Rules](./docs/policies.md) | 8 | Create masking policies and per-role rules. Tag-based ([Snowflake](https://docs.altr.com/data-sources/snowflake/policy-on-snowflake/), [Databricks](https://docs.altr.com/data-sources/databricks/policy-on-databricks/)) and [column-based](https://docs.altr.com/features/data-access-controls/data-masking/column-based-masking/) (Snowflake only). [Masking levels 10000–10009](https://docs.altr.com/features/data-access-controls/data-masking/masking-types/). Includes `get_roles` — list all ALTR roles (called [user groups](https://docs.altr.com/page-descriptions/user-groups/) in the ALTR console). |
| [Classification](./docs/classification.md) | 41 | Run automated [data classification scans](https://docs.altr.com/features/data-classification/). Snowflake (in-house + ALTR Native + GDLP), OLTP (ALTR Native + GDLP), Databricks (GDLP only). Includes findings-tree navigation and human review decisions. |
| [Access Management](./docs/access-management.md) | 4 | Access management policies for [Snowflake and OLTP](https://docs.altr.com/features/data-access-controls/access-management-policy/). |
| [Access Requests](./docs/access-requests.md) | 6 | Submit, approve, deny, and cancel data access approval requests. |
| [Audits](./docs/audits.md) | 6 | Search sidecar, Snowflake query, and platform [system audits](https://docs.altr.com/features/database-activity-monitoring/). |
| [Audit Reports](./docs/audit-report.md) | 17 | Create, schedule, and review structured audit report definitions and instances, including comments and sign-offs. |
| [DAM Alerting](./docs/dam-alerting.md) | 10 | Create match and threshold alert rules over sidecar and Snowflake audit events; triage, comment on, and acknowledge the alerts they fire. |
| [Telemetry](./docs/telemetry.md) | 9 | Monitor [ALTR sidecar proxy](https://docs.altr.com/data-sources/oltp/) agent and sidecar instance health. |
| [Sidecar Configuration](./docs/sidecar-config.md) | 37 | Configure the [ALTR sidecar proxy](https://docs.altr.com/data-sources/oltp/sidecar-integration/) — agents, repos, repo users, service users, sidecars, listeners, and bindings. |
| [Vault Tokenization](./docs/vault-tokenization.md) | 4 | Tokenize and detokenize values using ALTR vaulted tokenization. |
| [Critical Tokenization](./docs/critical-tokenization.md) | 4 | Tokenize and detokenize values using ALTR critical tokenization. |
| [Key Management](./docs/key-management.md) | 9 | Manage FPE encryption keys and tweaks. |

### Critical callouts

A few things are easy to miss and worth surfacing here:

**Snowflake tags vs Databricks tags.** A **Snowflake tag** is a first-class ALTR object — you register it with `connect_tag`, it gets a `tag_group_id`, and shows up in `get_tags`, `get_tag_details*`, `update_tag`, and `disconnect_tag*`. A **Databricks tag** is the opposite: not an ALTR object at all, just a raw string you pass into `create_policy` (with `policy_type="PUSHDOWN"` and `database_ids=[…]`). Databricks tags never appear in `get_tags` and do not have a `tag_group_id`. None of the Tags tools apply to Databricks.

**Databricks `create_policy` requirements.** When creating a masking policy for a Databricks metastore, you **must** pass `database_ids` as a list — even for a single database (e.g. `database_ids=[2167]`) — and set `policy_type="PUSHDOWN"`. Omitting `database_ids` or using `policy_type="TAG"` will be rejected by the API. Snowflake policies do the opposite: omit `database_ids` and let `policy_type` default to `TAG`.

## Data Source Support

Platform setup guides on the ALTR docs site:
- [Snowflake](https://docs.altr.com/data-sources/snowflake/)
- [OLTP databases](https://docs.altr.com/data-sources/oltp/) (PostgreSQL, MySQL, Oracle, SQL Server)
- [Databricks](https://docs.altr.com/data-sources/databricks/)

| Feature | Snowflake | OLTP (via sidecar) | Databricks |
|---|---|---|---|
| Database connections | ✅ | — | ✅ |
| Masking policies | ✅ | ❌ | ✅ |
| Classification | ✅ | ✅ | ⚠️ Partial |
| Access management policies | ✅ | ✅ | ❌ |
| Access requests | ✅ | ❌ | ❌ |
| Query audit logging | ✅ | ✅ | ❌ |
| System audit logging | ✅ | ✅ | ❌ |
| Sidecar configuration | — | ✅ | — |
| Telemetry & monitoring | — | ✅ | — |

**Legend:** ✅ Supported &nbsp; ⚠️ Partial &nbsp; ❌ Not supported &nbsp; — Not applicable

**Classification mode coverage:**

| Mode | Snowflake | OLTP | Databricks |
|---|---|---|---|
| In-house (ALTR pattern matching) | ✅ | ❌ | ❌ |
| ALTR Native classifiers | ✅ | ✅ | ❌ |
| GDLP (Google Cloud DLP) | ✅ | ✅ | ✅ |

**Databricks classification — Partial:** GDLP only via `create_databricks_job`; no in-house or ALTR Native classifiers. A `collection_name` may optionally be passed to scope the scan to a specific ALTR collection's classifiers (subject to `condition_types`); when omitted, all default Google DLP infoTypes are used.

**Access management policies (Databricks):** This MCP server does not currently expose Databricks grant or access management APIs. For Databricks access control, use the Databricks UI or REST API directly.

**OLTP** refers to relational databases (PostgreSQL, MySQL, Oracle, SQL Server) accessed through a customer-managed [ALTR sidecar proxy](https://docs.altr.com/data-sources/oltp/).

## Troubleshooting

### Checking which version you are running

```bash
uvx altr-mcp --version
```

This works without credentials. Your AI client also reports the same version as the server version when it connects, which is the quickest way to confirm the client actually picked up an upgrade.

### `uvx: command not found`

Install [uv](https://docs.astral.sh/uv/getting-started/installation/): `pip install uv` or via the [official installer](https://docs.astral.sh/uv/getting-started/installation/).

### Server not appearing in your AI client

Restart your AI client after editing the config file — changes are not picked up automatically.

### `ERROR: Missing required environment variables`

Verify `ORG_ID`, `MAPI_KEY`, and `MAPI_SECRET` are set in the `env` block of your client config. Variable names are case-sensitive.

### Tools returning `{"success": false, ...}`

| HTTP status | Likely cause | Fix |
|---|---|---|
| `401` | Invalid credentials | Verify `MAPI_KEY` / `MAPI_SECRET` in the ALTR console under **Settings > Preferences > API** |
| `403` | Feature not enabled for this organization | The endpoint exists but is gated by an ALTR feature flag your org doesn't have turned on. Contact ALTR support to confirm the feature is enabled for your account. |
| `404` | Resource not found | Confirm the ID exists in your organization |
| `429` | Rate limited | The server retries automatically up to 3× with backoff; if persistent, reduce request frequency |

### A tool is missing from the tool list

Check whether the tool name appears in the `RESTRICTED_TOOLS` env var in your client config. Restricted tools are hidden from the tool list entirely.

### A restricted tool is still exposed

`RESTRICTED_TOOLS` matches names exactly, so a misspelled or renamed entry restricts nothing. Check the server log for `tool_restriction_middleware.unknown_tools`, which names any entry that matched no registered tool.

### Timeouts on large result sets

Use pagination parameters (`limit`, `offset`, or `cursor`) available on audit, telemetry, and classification tools to reduce response size.

## Development

### Running Tests

```bash
# Install dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/integration/test_database.py

# Run a specific test
uv run pytest tests/integration/test_database.py::test_create_database_with_service_user

# Run with coverage report (terminal)
uv run pytest --cov=altr_mcp --cov-report=term-missing

# Run with coverage and generate an HTML report at htmlcov/index.html
uv run pytest --cov=altr_mcp --cov-report=html
```

### Project Structure

```
altr_mcp/
  server.py          # MCP server entrypoint and tool registration
  settings.py        # Pydantic settings (env vars)
  instructions.md    # System prompt for LLM tool guidance
  tools/             # Tool definitions (one file per domain)
  utils/             # API client functions (one file per API)
tests/
  unit/              # Unit tests (settings, models, annotations)
  integration/       # Integration tests (httpx mocks per domain)
```

## Learn More

**Platform setup**
- [ALTR documentation home](https://docs.altr.com)
- [Snowflake data source](https://docs.altr.com/data-sources/snowflake/)
- [OLTP data source](https://docs.altr.com/data-sources/oltp/)
- [Databricks data source](https://docs.altr.com/data-sources/databricks/)
- [Manage API keys](https://docs.altr.com/account-and-api/api/api-keys/)

**Data access controls**
- [Tag-based access policy — Snowflake and Databricks](https://docs.altr.com/features/data-access-controls/data-masking/tag-based-masking/)
- [Column-based access policy — Snowflake](https://docs.altr.com/features/data-access-controls/data-masking/column-based-masking/)
- [Masking policies (10000–10009 types)](https://docs.altr.com/features/data-access-controls/data-masking/masking-types/)
- [Access management policy & Managing Access Requests](https://docs.altr.com/features/data-access-controls/access-management-policy/)

**Discovery and observability**
- [Data Classification](https://docs.altr.com/features/data-classification/)
- [Database Activity Monitoring](https://docs.altr.com/features/database-activity-monitoring/)

**Protocol**
- [Model Context Protocol specification](https://modelcontextprotocol.io)

## License

Copyright (C) 2026 ALTR Solutions, Inc.

GNU General Public License v3.0 or later (`GPL-3.0-or-later`). See
[LICENSE.md](LICENSE.md) for the copyright notice and the full license text.
