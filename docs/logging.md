title: ALTR MCP Server Logging

# Logging

Every tool call is logged to stderr at `INFO` with its arguments, which is
what makes a session traceable. `LOG_LEVEL` sets the threshold and
`LOG_FORMAT` chooses between `console` (default) and `json`.

## What gets redacted

An argument is redacted when its value is a credential or user-supplied free
text. Identifiers, enums, and pagination cursors are logged in full, because
they are what you read a log line for. That includes identities — `email`,
`consuming_user_email`, `database_username`, `requester` — which are logged as
sent: they are how a call is attributed, and ALTR's own audit log records the
same values. If your log destination takes a different view of personal data
than your ALTR tenant does, that is the line to check.

| Redacted | Why |
|---|---|
| `values` | the plaintext being tokenized — `vault_tokenize(values={"ssn": ...})` is the secret itself |
| `text`, `comment`, `comments`, `attestation`, `justification` | human free text, where unannounced PII arrives |
| `statement_text_contains`, `filters`, `filter_tree` | an audit search term is a data value: someone hunting a value types that value, and the report-definition filter groups and DAM alert rule filter trees carry the same term |
| `connection_string` | a DSN embeds its password inline, as `user:pw@host` |
| `password`, `secret`, `credentials`, `passphrase`, `private_key`, `api_key`, `auth_token`, `access_key` | the bare credential names, which the suffix rule below does not match |
| anything ending `_password`, `_secret`, `_credential`, `_credentials`, `_private_key`, `_passphrase` | applied as a suffix rule, so a new argument with one of these suffixes is covered when it is added |

Dictionary keys survive, so a line reads
`values={'ssn': '<redacted>', 'email': '<redacted>'}` — you keep which fields
were sent and lose the data. An argument that was omitted logs as `None`
rather than `<redacted>`, so "the caller left it out" stays distinguishable
from "a secret was sent and hidden".

**Tokens are not redacted.** `tokens`, `token`, `page_token` and
`next_page_token` are logged in full. A token exists to be handled freely —
that is what tokenizing produces — and ALTR's own Shield audit log is keyed by
token. The paging ones are cursors.

## Why redaction is keyed on the argument name

Not on the tool name. A list of tool names is only correct until the next tool
is added; a list of argument names covers a new tool the day it is written.
The suffix rule extends that further, so `*_password` needs no maintenance at
all.

## One pipeline

This package logs through structlog; its dependencies log through the standard
library. Those are two separate systems, and rendering them independently meant
`LOG_FORMAT` described only part of the output and a guard could be installed
in one pipeline while data travelled through the other.

structlog now hands its records to a stdlib formatter rather than writing them
itself, so a single handler renders both. Practical effects:

- Dependency lines honor `LOG_FORMAT`. Under `json` everything on the stream is
  a JSON object — the fastmcp startup banner is suppressed in that mode, since
  it is rich-rendered ASCII art and the one thing a JSON parser cannot read.
- Every line names the logger it came from, so a warning can be attributed to
  the dependency that raised it.
- Dependency lines carry the `correlation_id` of the tool call they happened
  inside, so an HTTP retry can be tied to the call that caused it.
- There is one place to install a guard.

`fastmcp` installs handlers on its own logger and sets `propagate = False`.
Those are reclaimed at startup — an application owns its logging policy, and
otherwise its records bypass the handler everything else goes through.

## Where redaction applies

Argument data can reach a log by more than one route, so each is covered:

- **The invocation line** — arguments are redacted as above.
- **Tracebacks.** Frame locals hold tool arguments. Under `json` the traceback
  transformer is configured with `show_locals=False`; under `console` the
  traceback comes from `format_exc_info`, which never emits locals.
- **Query strings.** A tool argument can travel in a URL — `search_audits`
  sends `statement_text_contains` that way — and httpx logs each request at
  `INFO` with the URL it assembled. Argument-name redaction cannot reach that,
  so per-request httpx logging is held at `WARNING`.
- **Argument coercion.** Arguments are validated before the tool body runs, and
  a validation error names the value it rejected.
  `ValidationRedactionMiddleware` builds the caller-facing error from the field
  path and message only, and a processor in the render chain strips rejected
  values from anything about to be written. fastmcp reports these errors in
  different forms across the versions this package allows, and each is covered.
- **Debug logging.** Dependencies print raw requests and responses at `DEBUG`,
  tool arguments and results included. Below `INFO`, the handler writes only
  this server's own lines, so `LOG_LEVEL=DEBUG` adds detail from this server's
  code and nothing else, whatever `FASTMCP_LOG_LEVEL` asks for.

The argument-coercion guard is a processor rather than a `logging.Filter` for a specific
reason: the value travels inside an exception that is rendered from `exc_info`
by the chain itself, so a filter editing the record never sees it.

## What is never logged

Tool results. `_summarize` emits only a count or `ok`, so a `vault_detokenize`
response full of plaintext logs as `3 items`. `MAPI_KEY` and `MAPI_SECRET` are
`SecretStr` and render as `**********` wherever they appear.
