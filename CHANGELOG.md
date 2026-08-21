# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Review-gated classification jobs. `create_job`, `create_gdlp_job`,
  `create_databricks_job` and `create_oltp_job` accept `requires_review`,
  which holds the report until every finding is decided. Two new tools
  finish the review: `confirm_job_report` releases the report and
  `cancel_job_report` abandons it.
- `record_bulk_job_decision` approves or rejects every undecided finding
  matching a filter of classifiers, confidence tiers and a database path,
  with a `dry_run` option that returns the counts first.
  `revoke_bulk_job_decision` undoes one.
- `get_job_findings_leaves` lists every finding in a job in one paginated
  stream, optionally filtered by confidence tier.
- DAM Alerting tools (10): create, list, get, update and delete alert rules,
  and list, get, acknowledge and comment on the alerts they fire. See
  `docs/dam-alerting.md`.
- `ALTR_DAM_ALERTING_BASE_URL` overrides the DAM Alerting endpoint, which
  defaults to `https://<ORG_ID>.dam-alerting.live.altr.com/v1/dam-alerting`.
- `SUPPORT_MODE` — a read-only mode for support and field engineering
  investigations. When enabled, only the 71 lookup tools are exposed, plus an
  inert `enter_support_mode` on stdio; the 85 tools that create, update,
  delete, disconnect, register, deregister, trigger, approve, deny, restore,
  revoke, rotate, import, tokenize, or detokenize are removed from
  `tools/list` and rejected on `tools/call`. Enabling it also appends
  `altr_mcp/instructions_support.md` to the server instructions sent to the
  client. Composes with `RESTRICTED_TOOLS`; both filters apply. See
  `docs/support-mode.md`.

  The allow-list is deliberately not derived from `readOnlyHint`. The four
  detokenization tools carry that annotation and are still withheld, because
  they return real customer values rather than configuration; the three
  `search_*` audit tools carry no annotation and are still included, because
  they POST a search request rather than issuing a GET.

- Runtime support mode, for operators who will not edit a config file. Three
  tools reach the same enforcement without an env var or a restart:
  `enter_support_mode` arms the allow-list mid-session,
  `request_write_unlock` releases exactly one named tool for exactly one call
  and then re-latches, and `exit_support_mode` restores everything given a
  confirmation phrase the operator types. Tool visibility changes take effect
  immediately via a `tools/list_changed` notification. `exit_support_mode`
  returns a log of every unlock granted and write executed during the session.

  A mode set by the operator through `SUPPORT_MODE` cannot be unlocked or
  exited by any tool; leaving it still means restarting without the flag. Only
  a mode the session armed itself can be stood down by the session. The
  detokenization tools and the two token-delete tools are never unlockable at
  any scope. These three tools refuse to run on the `sse` and
  `streamable-http` transports, where one process can serve several clients
  and a per-process latch would restrict all of them.

- `SUPPORT_PROMPTS` — publishes eight troubleshooting prompts over
  `prompts/list`, one per common support symptom, each beginning by instructing
  the client to call `enter_support_mode`. Serving them from the server rather
  than a wiki page means the guardrail cannot be edited out in transit and the
  wording versions with the release.

  Off by default. A published prompt appears in every user's prompt menu as
  soon as they upgrade, which makes publishing one a customer-facing change
  rather than something that should arrive with a version bump, and it lets a
  prompt be validated against real cases before anyone outside a pilot can
  reach it.

  `enter_support_mode` is available under `SUPPORT_MODE` as well, where it is a
  no-op reporting the mode is already on, so a prompt whose first instruction is
  to call it reads correctly under both paths. `request_write_unlock` and
  `exit_support_mode` remain withheld there.

  `SUPPORT_PROMPTS` also appends a short instruction block telling the assistant
  to arm support mode before troubleshooting, which covers ad-hoc questions and
  not only the eight prompts. It is gated with the prompts rather than shipped to
  everyone, because it steers the model to withhold writes and a user who never
  opted in should not have to be walked through the exit phrase to undo that.

  Both the prompts and that instruction block are published on the `stdio`
  transport only, since the control tools refuse on `sse` and `streamable-http`
  and an arming-first prompt would otherwise fail at its first step. Use
  `SUPPORT_MODE` on those transports.

### Changed
- Classifiers are defined through `compound_ruleset` only, and
  `create_classifier` now requires it. A regex classifier is a ruleset with
  a single ROW_DATA condition carrying the pattern and its
  `minimum_threshold`; sampling is configured on the job.
- `update_classifier` with a `compound_ruleset` also removes any legacy
  top-level pattern, so the ruleset alone decides matches. Include a
  ROW_DATA condition to keep a legacy regex. Classifiers not updated keep
  their existing definition.
- `ToolRestrictionMiddleware` accepts an optional `allowed_tools` allow-list
  alongside the existing `restricted_tools` deny-list. Allow-list semantics
  fail closed: a tool added in a future release is unavailable in support mode
  until it is added to `SUPPORT_ALLOWED_TOOLS` on purpose. Blocked-tool errors
  now name which filter withheld the tool.
- `ToolRestrictionMiddleware` also accepts a `SupportModeController`, which
  supplies the allow-list live rather than at construction. Where a static
  allow-list and a controller are both present the intersection applies, so
  neither can widen the other, and `RESTRICTED_TOOLS` still outranks both. A
  granted unlock therefore cannot reach a tool the operator denied.

### Removed
- The `pattern`, `minimum_threshold` and `sample_size` parameters of
  `create_classifier` and `update_classifier`.

### Fixed
- The classification job tools describe only the option values the API
  accepts: `job_type` is `FULL` or `INCREMENTAL`, `create_oltp_job`'s
  `sample_strategy` is `ROWS`, `METADATA` or `COMBINED`, and `sample_type`
  is `ROWS` or `PERCENT`. `ENTROPY` is listed as a condition type and a
  classifier condition target.
- The job tools describe `condition_types` as the full set of targets to
  evaluate, which replaces the server default rather than adding to it.
- `create_oltp_job` with `sample_strategy` `METADATA` no longer sends
  sampling fields, which the API rejects for a metadata scan, and with
  `sample_type` `PERCENT` it asks for `sample_size` instead of sending the
  row-count default.

## [0.7.1]

### Security
- Under fastmcp 3.3 and later, a rejected tool argument's value could reach
  the log, and under fastmcp 3.4.3 and later also the error returned to the
  caller. Those versions report validation failures in forms the 0.7.0 fix did
  not cover. A fresh install of 0.7.0 resolves to an affected fastmcp version.

- Debug output from dependencies no longer reaches the log. Below `INFO`, only
  this server's own lines are written, whatever `LOG_LEVEL` or
  `FASTMCP_LOG_LEVEL` asks for. Libraries such as fastmcp, the MCP SDK and
  sse-starlette print raw requests and responses at `DEBUG`, which redaction
  cannot reach.

- Logs written by 0.7.0 under fastmcp 3.3 or later, or by any version with
  debug logging enabled, may hold argument values that failed validation, or
  whole requests and, under the `sse` and `streamable-http` transports, whole
  responses. That includes plaintext sent to the tokenize tools and returned by
  the detokenize tools. Review who can read them and how long they are kept.

## [0.7.0]

### Added
- `docs/logging.md` — what is logged, what is redacted, and where each guard
  sits.

### Changed
- All log output now goes through one pipeline. This package uses structlog
  and its dependencies use the standard library, and the two were rendered
  independently — so a single `LOG_FORMAT=json` run emitted three different
  formats on one stream, and only this package's own lines were actually JSON.
  structlog now hands its records to a stdlib formatter instead of writing
  them itself, so one handler renders both.

  Operator-visible consequences, all improvements but all changes:
  - Dependency log lines (httpx, fastmcp, uvicorn) now honor `LOG_FORMAT`.
    Under `json` they are JSON objects with `event`, `level` and `timestamp`,
    where before they were plain text, and in one case ANSI-coloured.
  - Those lines also carry the `correlation_id` bound for the tool call they
    occurred inside, so a retry or a transport warning can be tied to the
    call that caused it.
  - `fastmcp` installs handlers on its own logger and stops propagation;
    those are reclaimed at startup, because an application owns its logging
    policy. uvicorn does the same thing later, when an HTTP transport
    starts, so it is now told not to configure logging at all.
  - httpx's per-request line is held at `WARNING` and so no longer appears
    at `INFO` (see the security note below). It carried the upstream host,
    path and status, which no tool event reports, so an `upstream_request`
    line replaces it — the same facts, built from the base URL, with the
    query string never interpolated in.
  - Every line now names the logger it came from. One handler renders four
    sources, and the format string this replaced carried `%(name)s`.
  - Under `LOG_FORMAT=json` the fastmcp startup banner is suppressed. It is
    rich-rendered ASCII art, and the one thing on the stream a JSON parser
    cannot read.

  Anything parsing this server's stderr should be re-checked against the new
  output. The change is what makes the redaction below installable in one
  place instead of several.

### Security
- Tool arguments carrying credentials or user-supplied free text are no longer
  written to the log. Every tool call is logged at `INFO` with its arguments,
  and some tools take a secret or a plaintext value *as* an argument, so an
  unredacted argument line could carry it.

  Redacted: `values`, `text`, `comments`, `attestation`, `justification`,
  `statement_text_contains`, `filters`, `connection_string`, the bare
  credential names (`password`, `secret`, `credentials`, `passphrase`,
  `private_key`, `api_key`, `auth_token`, `access_key`), and any argument
  ending `_password`, `_secret`, `_credential`, `_credentials`,
  `_private_key` or `_passphrase`. Redaction is keyed on the argument name
  rather than the tool name, so a new tool taking one of these is covered when
  it is written; the suffix rule covers credential-bearing names nobody
  enumerated; and it recurses, since several tools take caller-shaped nested
  payloads where a matching name one level down is the same credential.

  Dictionary keys survive, so which fields were sent stays visible while their
  values do not. An omitted argument still logs as `None` rather than
  `<redacted>`, so "the caller left it out" remains distinguishable. Tokens are
  deliberately not redacted: a token exists to be handled freely, ALTR's Shield
  audit log is itself keyed by token, and `page_token`/`next_page_token` are
  cursors.

- Tracebacks no longer serialize frame locals. Locals hold tool arguments, so
  serializing them bypassed the redaction applied to the argument line. Under
  `json` the traceback transformer sets `show_locals=False` explicitly rather
  than relying on a library default that has changed before; under `console`
  the traceback is rendered by `format_exc_info`, which never emits locals.
  The safe renderer is installed at import time as well, and writes to stderr
  rather than stdout, so a consumer importing the decorator without
  configuring logging neither leaks nor corrupts the stdio transport.

- Tool arguments sent in a request's query string are no longer written to the
  log. httpx logs each request URL at `INFO`, and argument-name redaction
  cannot reach a URL a dependency builds. Per-request httpx logging is held
  at `WARNING`, which also covers query parameters added later.

- Validation failures no longer repeat the value they rejected, on either the
  caller-facing error or the log. Argument coercion happens above this
  package's own decorator, so it needs handling at two layers: a new
  `ValidationRedactionMiddleware` builds the returned error from the field path
  and message only, and a processor in the render chain strips rejected values
  out of anything about to be written — including a traceback rendered from a
  dependency's exception, which is where the value actually travels.

- **Operators upgrading from 0.6.0 or earlier should rotate any credential
  passed through a tool argument — it may be in their logs.** In practice
  `database_password` (`create_database`, `create_databricks_database`,
  `update_database`) and `connection_string` (`update_database`). Logs from
  those versions may also hold plaintext passed to the tokenize tools and
  free-text arguments, so review who can read them and how long they are kept.

  Tool results were already safe: only a count is logged, never the payload.

- Bumped transitive dependencies flagged by the Trivy vulnerability scan:
  `anyio` 4.13.0 → 4.15.1 (CVE-2026-63374, CVE-2026-64847) and `pyjwt`
  2.13.0 → 2.15.1 (one critical and five high advisories, among others).
  The previous `pyjwt` bump to 2.13.0 is no longer sufficient.

## [0.6.0]

### Added
- `REQUEST_TIMEOUT` sets the per-request timeout in seconds (default `30`),
  which was previously hardcoded. `MAX_RETRY_AFTER` bounds a server-sent
  `Retry-After` (default `60`). Both are documented in the README, and
  `docs/error-handling.md` now describes the retry and timeout behavior
  instead of stating that `Retry-After` is honored verbatim.

### Changed
- **Breaking (configuration):** `MAX_RETRIES` must now be `>= 1` and
  `MAX_RETRY_AFTER` must be `> 0`; the server refuses to start otherwise, so a
  deployment that sets either to `0` will fail to boot after upgrading.
  `stop_after_attempt(0)` previously made one attempt anyway, so `MAX_RETRIES=0`
  silently behaved like `1`. Migration: set `MAX_RETRIES=1` for "try once, never
  retry", or `DISABLE_RETRY=true` to skip the retry path entirely. Neither
  setting accepts `inf` or `nan` any longer — pydantic treats both as valid
  floats, and an infinite ceiling silently removes the bound it exists to
  impose.
- API calls share one `httpx.AsyncClient` per event loop instead of building
  one per request, so connections and TLS sessions are reused rather than
  discarded on every call and every retry. `get_job_report`'s presigned
  download shares it too, which also moves it off httpx's 5s default timeout.
  Two consequences worth knowing: the pool is now process-wide (100
  connections), so a saturating burst can surface as `PoolTimeout` on an
  unrelated call, and the shared client rejects all cookies — without that, a
  `Set-Cookie` from any one call (ALB stickiness, a WAF challenge) would replay
  on every later call to that host, which a per-request client could never do.

### Fixed
- Retry backoff no longer blocks the event loop. `_async_sleep` was declared
  `async` but delegated to `tenacity.nap.sleep`, which is `time.sleep`, so a
  single call waiting out a 429 stalled every other in-flight tool call for
  the length of its backoff — measured at zero progress on a concurrent task
  during a one-second wait. It now awaits `asyncio.sleep`. The test seam moved
  with it: the retry tests patched `tenacity.nap.sleep`, and because that hook
  is synchronous, a blocking implementation satisfied them. They now patch
  `api._async_sleep`, and two tests cover it — one driving the coroutine by
  hand to prove it suspends, one asserting other tasks progress during a
  backoff.
- A server-sent `Retry-After` is clamped to `MAX_RETRY_AFTER`. It was honored
  verbatim, and since every attempt counts against `MAX_RETRIES`, a
  `Retry-After: 86400` would have parked the call for a day with nothing to cut
  it short. Non-finite values are rejected rather than clamped: `nan` parses as
  a float, survives a `< 0` test, and survives `min()` too — every comparison
  against NaN is false, so `min(nan, 60.0)` is `nan` — and `asyncio.sleep(nan)`
  never wakes, which would have made the clamp meant to bound the wait the
  cause of an unbounded one.
- The locally computed backoff is bounded by the same ceiling.
  `wait_exponential_jitter`'s own default max is ~4.6e18 seconds, so raising
  `MAX_RETRIES` reintroduced an effectively unbounded wait on the path the
  client controls — at `MAX_RETRIES=10` the last wait actually taken is
  attempt 9's, around 256 seconds.
- `get_client()` is guarded by a lock and keyed by event loop rather than held
  in a single slot. Unsynchronized, a thread switch mid-update could hand back
  a client bound to another live loop, which raises `RuntimeError: ... bound to
  a different event loop` from inside httpx; a single slot also meant two live
  loops evicted each other's client on every lookup, losing the reuse the cache
  exists for. Every tool is `async` today so nothing runs on a worker thread,
  making this latent rather than live.
- `get_job_report` no longer discards the cause of either failure it can
  meet. An expired presigned URL reports its HTTP status: S3 answers one with
  a 403 and an XML body, so the unguarded `resp.json()` surfaced a
  `JSONDecodeError`. A failed report *creation* never got that far — the
  response carries no `url`, so `job_url["url"]` raised `KeyError: 'url'` and
  threw away the real 404. Both now return the documented
  `{success, status_code, message}` shape.
- Exceptions that stringify to nothing no longer produce a dangling message
  like `"PoolTimeout: "`, and the failing URL is logged alongside.

## [0.5.7]

### Added
- CI now runs the test suite on every Python version `requires-python`
  permits — 3.11, 3.12, 3.13 and 3.14 — and the classifiers list all four.
  Previously CI tested only 3.11, the classifiers stopped at 3.12, and 3.13
  and 3.14 were permitted by the metadata, advertised nowhere and never run.
  A test keeps the matrix, the classifiers and `requires-python` in step.

### Security
- Bumped `cryptography` 49.0.0 -> 50.0.0 to clear CVE-2026-69247 (HIGH). It
  reaches us transitively through `authlib`, `joserfc` and `secretstorage`,
  none of which cap the version, so a lockfile bump was enough -- no
  direct dependency was added.

### Changed
- `LICENSE.md` now carries a copyright notice for ALTR Solutions, Inc. and an
  `SPDX-License-Identifier`. It was the bare 595-line GPLv3 text with no
  copyright line and no version election, so nothing in the repository recorded
  which GPL grant applied — `pyproject.toml` said `GPL-3.0-or-later` and GitHub,
  reading only the license file, detected the ambiguous `GPL-3.0`.
  `GPL-3.0-only` and `GPL-3.0-or-later` are different grants and the license
  text is identical either way, so a notice is the only place the choice can
  live. A test now keeps the notice, `pyproject.toml` and the README in
  agreement.

- The server instructions sent to the model no longer enumerate individual
  tools. They said "These tools cover four areas" and then listed ten groups
  across 61 lines, naming 98 tools — 58 of the 156 registered ones appeared
  nowhere, and four whole domains were missing: Audit Reports, Vault
  Tokenization, Critical Tokenization, and Key Management. A domain absent
  from that text is one the model is less likely to reach for.

  In place of the list: a verb table (`get_`/`list_`, `create_`/`add_`,
  `disconnect_` versus `delete_`, `trigger_`, `search_`) so an unfamiliar
  tool's behavior is predictable, the `sc_` convention for sidecar
  configuration, and all 13 domains with one line each. The tool list the
  client already receives carries every name and description and is
  authoritative, so re-listing them added tokens and a list that was
  guaranteed to fall behind.

- `publish-mcp` no longer rewrites `server.json` from the tag before
  publishing. The committed file is what reaches the MCP Registry, and the job
  now checks it records the version being released instead of overwriting it.

  Stamping is what let that file rot for several releases: a wrong value had
  no consequence, so nothing ever surfaced it. It is safe to stop because the
  agreement is established before `publish-mcp` runs — the `test` job asserts
  `server.json` matches the newest `CHANGELOG.md` section, `verify-release`
  asserts the tag matches that same section, and `publish` needs both. That
  chain is now asserted by a test of its own, since dropping a link would
  silently remove the guarantee.

### Fixed
- `README.md` documented 9 of the 20 available settings. `MAX_RETRIES`,
  `DISABLE_RETRY` and all seven per-service endpoint overrides were
  undiscoverable without reading `settings.py`. The endpoint defaults derive
  from `ORG_ID` rather than from `ALTR_API_BASE_URL`, and four carry a
  version path segment; both are now documented accurately.
- Six `README.md` links pointed at `docs.dev.altr.com`, ALTR's dev
  documentation environment, from a file rendered on the PyPI project page.
  One link began `hhttps://` and could not be followed at all.

- The release gate treated any `## [...]` heading as a release, so a
  `## [Unreleased]` section at the top of `CHANGELOG.md` would have failed
  every release — with an error suggesting the tag be `Unreleased`. That
  heading is the standard Keep a Changelog convention, which this file's own
  header says the project follows, so it was a trap waiting for whoever
  adopted it. Only `MAJOR.MINOR.PATCH` headings count as releases now, and a
  changelog with no release section names the rename in the error rather than
  reporting the section merely absent.

  This also makes the two readers of this file agree. The `server.json` guard
  already matched semver headings only; the release gate did not, so they
  would have disagreed about which section was newest.

## [0.5.6]

### Security
- `mcp-publisher` is now pinned to a specific release (`v1.8.0`) and verified
  against a committed SHA-256 digest before it runs. It was fetched from
  `releases/latest` with no version pin, no checksum, and no `curl --fail`,
  then piped straight into `tar` and executed — in the job that holds
  `id-token: write` for the `io.github.altrsoftware` registry namespace. Any
  upstream release, or a replaced asset on an existing one, silently changed
  what we ran with permission to publish as us. Without `--fail`, an error
  page would also have been fed to `tar` as if it were the binary.

  The digest is committed here rather than taken from the release's
  `checksums.txt`, which would only have caught a corrupt download: anyone
  able to replace the tarball can replace the checksum file beside it.

### Fixed
- The `publish` and `publish-mcp` jobs ran with different permissions for no
  stated reason: both check out the repository, but only `publish-mcp`
  declared `contents: read`. A job-level permissions block replaces the
  workflow-level one outright, so this was a real difference rather than a
  cosmetic one. They now match.

## [0.5.5]

### Added
- Documentation is now checked against the live tool registry in CI. Tool names
  in `README.md`, `docs/`, `.env.example`, and `altr_mcp/instructions.md` must
  resolve to a registered tool, and every "N tools" claim must match what
  `register_all` actually registers. A new tool module fails the suite until it
  has a domain doc and a row in both documentation tables.
- `server.json` is now checked against the newest `CHANGELOG.md` section, so the
  version recorded there can no longer drift. It was stale going into this
  release, as it has been going into most of them.
- `verify-release` now requires the tag's `CHANGELOG.md` section to be the
  newest one, not merely present somewhere in the file. The old check would
  have passed a `v0.5.4` tag today, re-releasing an already-published version,
  because a non-empty `## [0.5.4]` section still exists further down. The
  check moved out of the workflow YAML into
  [`scripts/check_changelog.py`](scripts/check_changelog.py) so it can be unit
  tested — as inline shell it only ever ran during a live release, which is why
  the gap survived.

### Fixed
- The MCP handshake reported FastMCP's own version as `serverInfo.version`
  (3.2.4) rather than the package version (0.5.4). The server is now
  constructed with `version=`, so every client sees the real version. Anyone
  who read the server version from a client — to check an upgrade landed, or
  in a bug report — was reading the framework's version number.
- `altr-mcp --version` and `--help` were silently ignored: the flags were never
  parsed, so the server started on stdio instead. Interactively that looked
  like a hang, since the process sat waiting for MCP traffic on stdin. Both
  flags now work, and neither requires `ORG_ID`/`MAPI_*` to be set. An
  unrecognized flag is now an error rather than an unexpected server start.
- The PyPI package summary advertised "135 tools across 13 domains"; the server
  registers 156.
- The README domain table listed 9 of 13 domains and summed to 93 tools under a
  heading claiming 156. Access Requests, Audit Reports, Vault Tokenization,
  Critical Tokenization, and Key Management were missing entirely, and
  Classification was listed as 13 tools instead of 36.

## [0.5.4]

### Added
- Tag pushes now run a `verify-release` job that fails the release if the built
  version disagrees with the tag, or if `CHANGELOG.md` has no non-empty section
  for it. `publish` depends on it and `publish-mcp` depends on `publish`, so
  nothing downstream runs when it fails.
- A `RESTRICTED_TOOLS` entry matching no registered tool is now logged as a
  warning naming the entries, the first time a client lists tools, instead of
  being silently ignored.

### Fixed
- The `RESTRICTED_TOOLS` example in `.env.example` still listed
  `delete_database` and `delete_tag`, renamed to `disconnect_*` in 0.4.0. The
  middleware matches names exactly, so an operator who copied that example
  restricted two of the four tools they asked for and left the other two fully
  callable.

## [0.5.3]

### Fixed
- The package version is now derived from the git tag at build time
  (`uv-dynamic-versioning`) instead of being hardcoded in `pyproject.toml`.
  Tagging a release no longer requires a separate version bump commit, and the
  PyPI upload can no longer fail because `pyproject.toml` still carries the
  previously published version — which is what happened to `v0.5.2`. Builds
  outside a git checkout fall back to version `0.0.0+unknown`. The local version
  segment is deliberate: PyPI rejects any version carrying one, so a build
  environment that cannot read the tag fails the release rather than publishing
  a wrong version.

### Changed
- The release workflow now stamps the tag into `server.json` (`.version` and
  `.packages[].version`) before publishing to the MCP Registry, so the git tag
  is the single source of truth for the PyPI version and the registry entry
  alike. The values committed in `server.json` record the next intended
  release; they are not an input to the publish job.
- Documented the release procedure and its `git` prerequisite in
  [docs/releasing.md](docs/releasing.md).
- Removed broken documentation links from the README.

### Security
- Bumped the transitive `mcp` (MCP Python SDK) dependency 1.27.1 → 1.28.1 to
  resolve three HIGH severity CVEs flagged by the Trivy scan: CVE-2026-59950
  (WebSocket transport lacks Host/Origin validation), CVE-2026-52870
  (experimental task handlers allow cross-client task access/cancel), and
  CVE-2026-52869 (HTTP transports serve sessions without verifying the
  principal).

> `v0.5.2` was tagged but never published to PyPI or the MCP Registry — its
> changes ship in 0.5.3.

## [0.5.1]

### Added
- Published to the official MCP Registry (`io.github.altrsoftware/altr-mcp-server`).
  Added the `mcp-name` ownership token to the README so the registry can verify
  the PyPI package, and a `publish-mcp` GitHub Actions job that publishes to the
  registry via GitHub OIDC on each `v*` tag.

### Changed
- Migrated `server.json` to the current registry schema
  (`2025-12-11`): camelCase package fields, string `repository.id`, and a
  registry-compliant description (≤100 chars).

## [0.5.0]

### Fixed
- `create_gdlp_job` (Snowflake GDLP) posted to the removed `POST /v1/jobs/gdlp`
  endpoint, causing every call to fail with HTTP 500 after retry exhaustion. It
  now posts to `POST /v1/jobs/snowflake` with `classification_type: "gdlp"`, the
  current Classification API contract.
- `create_job` (ALTR-native Snowflake) posted to the deprecated generic
  `POST /v1/jobs` endpoint. It now posts to `POST /v1/jobs/snowflake` with
  `classification_type: "altr_native"`.

### Added
- `create_gdlp_job` now accepts optional `collection_name` (to scope which
  Google DLP infoTypes are inspected), `sample_size`, and `sample_type`.
- `create_databricks_job` now accepts optional `collection_name` to scope the
  GDLP infoTypes evaluated for a Databricks workspace scan.

### Security
- Bumped transitive/direct dependencies flagged by the Trivy vulnerability
  scan: `joserfc` 1.6.5 → 1.7.2 (CVE-2026-48990, JWS payload resource
  exhaustion) and `pydantic-settings` 2.14.1 → 2.14.2 (GHSA-4xgf-cpjx-pc3j,
  `NestedSecretsSettingsSource` symlink traversal outside `secrets_dir`).

## [0.4.0]

### Added
- `create_oltp_job` tool for running on-demand classification scans on OLTP
  databases (Oracle, MSSQL, MySQL, PostgreSQL) via a sidecar classification
  agent, wired to `POST /v1/jobs/oltp`. `create_job` remains Snowflake-only
  (it requires a numeric `database_id`, which OLTP sidecar repos do not have).
- `create_gdlp_job` tool for Snowflake GDLP (Google DLP) classification scans,
  wired to `POST /v1/jobs/gdlp`. A separate job type from ALTR-native
  `create_job` — it does not use a classifier collection.

### Changed
- Renamed 11 tools from `delete_*` to `disconnect_*` to distinguish removing an
  object from ALTR's view (the object still exists externally) from destroying
  the object itself:

  | Old name | New name |
  |----------|----------|
  | `delete_database` | `disconnect_database` |
  | `delete_tag` | `disconnect_tag` |
  | `delete_tag_by_details` | `disconnect_tag_by_details` |
  | `delete_sc_agent` | `disconnect_sc_agent` |
  | `delete_sc_repo` | `disconnect_sc_repo` |
  | `delete_sc_repo_user` | `disconnect_sc_repo_user` |
  | `delete_sc_service_user` | `disconnect_sc_service_user` |
  | `delete_sc_sidecar` | `disconnect_sc_sidecar` |
  | `delete_sc_sidecar_binding` | `disconnect_sc_sidecar_binding` |
  | `delete_agent_instance` | `disconnect_agent_instance` |
  | `delete_sidecar_instance` | `disconnect_sidecar_instance` |

  Truly destructive tools keep `delete_*` (`delete_policy`, `delete_rule`,
  `delete_classifier`, `delete_collection`, `delete_sc_agent_task`,
  `vault_delete_tokens`, `critical_delete_tokens`, `delete_task_telemetry`).
  Migration: update any `RESTRICTED_TOOLS` configuration or client code that
  references the old `delete_*` names.

### Security
- Bumped transitive dependencies flagged by the Trivy vulnerability scan:
  `starlette` 1.0.0 → 1.3.1 (CVE-2026-48710), `cryptography` 48.0.0 → 49.0.0
  (GHSA-537c-gmf6-5ccf), `pyjwt` 2.12.1 → 2.13.0 (CVE-2026-48526), and
  `python-multipart` 0.0.28 → 0.0.32 (CVE-2026-53539).
