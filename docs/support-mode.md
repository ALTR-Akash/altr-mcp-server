# ALTR MCP Support Read-Only Mode

Support mode exposes only the 71 lookup tools and withholds the other 85:
everything that changes state, plus the four detokenization tools, which
change nothing but return real customer values. Set `SUPPORT_MODE=true` to
enable it.

On stdio, `tools/list` reports 72 in that mode: the 71 lookups plus
`enter_support_mode`, which is present but inert there so that a prompt whose
first instruction is to call it still reads correctly. On the HTTP transports it
reports 71, since mode control refuses there and offering the tool would mean
advertising a call that can only fail.

It exists for support and field engineering work, where the job is to read
configuration and audit history in order to explain a customer's problem, and
where an accidental write would be a production incident.

## What it does

Two things, together:

1. **Restricts the tool set.** The 85 tools that create, update, delete,
   disconnect, register, deregister, trigger, approve, deny, restore, revoke,
   rotate, import, tokenize, or detokenize are removed from `tools/list` and
   rejected on `tools/call` with a `support read-only mode` error.
2. **Appends operating instructions.** The contents of
   `altr_mcp/instructions_support.md` are appended to the server instructions
   sent to the client, so the assistant is told what the mode is for and what
   the remaining tools cannot tell it.

The second half matters as much as the first. Blocking writes stops a bad
action; the instructions stop a wrong conclusion, which in support work is the
more common failure.

## Enabling it

```shell
export SUPPORT_MODE=true
```

Or in a client config:

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
        "SUPPORT_MODE": "true"
      }
    }
  }
}
```

`SUPPORT_MODE` and `RESTRICTED_TOOLS` compose. Both filters apply, so
`RESTRICTED_TOOLS` can withhold further tools from an already restricted set.

## Arming it without editing a config file

`SUPPORT_MODE` requires editing a client config and restarting. The operators
most in need of a guardrail are the least likely to do that correctly, and a
mistyped `RESTRICTED_TOOLS` entry looks exactly like a working one. So the same
enforcement can be armed from inside a session, by tool call:

| Tool | Effect |
| --- | --- |
| `enter_support_mode` | Arms the allow-list for the rest of the session. |
| `request_write_unlock(tool_name, reason)` | Releases one named tool for one call, then re-latches by itself. |
| `exit_support_mode(confirmation)` | Restores every tool, given the confirmation phrase. Returns the session log. |

Every prompt this server publishes opens by telling the client to call
`enter_support_mode`, so choosing a troubleshooting prompt is what arms the
guardrail. Prompts are published only when `SUPPORT_PROMPTS=true`; see
Publishing the prompts below. Tool visibility updates immediately through
a `tools/list_changed` notification, so withheld tools disappear from the
client rather than failing when called.

### The two paths are not equally reversible

This is the central design decision. A mode the **operator** set through
`SUPPORT_MODE` is hard: no tool can unlock a write or leave the mode, and
`request_write_unlock` and `exit_support_mode` are withheld from the tool list
entirely. Leaving it means restarting without the flag. A decision made in
configuration must not be reversible by the model it was meant to constrain.

A mode the **session** armed itself is soft, and the same session can stand it
down. That is not a weakness so much as the price of it costing nothing to arm.

### What the runtime path does and does not buy

It buys the turn-two failure, which is the one that actually happens. A
diagnosis that ends "you need to remove these four objects" is followed by "ok,
do it", and at that point the destructive path and the cooperative path look
identical. With the mode armed, that call fails in middleware rather than
depending on the assistant re-reading an instruction from earlier in the
conversation.

It does not buy the arming itself. Something has to call
`enter_support_mode`, and that something is the model. That is weaker than an
env var read at startup, and it is why the env var still exists for anyone who
wants a guarantee rather than a default. Once armed, though, the two are the
same code path: there is no softer kind of check.

The exit confirmation is a speed bump, not a gate. The server cannot tell a
phrase the operator typed from one the model typed, and the phrase is not a
secret: it appears in the tool docstring, in this document, and in the success
payload. What it buys is that a novice cannot be walked into a full exit
silently, because the model has to surface the request. It does not prevent a
model that decides to exit from exiting. The unlock-and-relatch path is the part
that is genuinely enforced, which is why it is the one to prefer.

Two hard limits, independent of how the mode was armed:

* **Detokenization is never unlockable.** `vault_detokenize`,
  `vault_partial_detokenize`, `critical_detokenize`,
  `critical_partial_detokenize`, `critical_delete_tokens`, and
  `vault_delete_tokens` cannot be reached through an unlock at any scope. No
  troubleshooting step requires plaintext, so "just this one call" is never a
  good enough reason.
* **`RESTRICTED_TOOLS` outranks an unlock.** The operator's deny-list cannot be
  widened from inside a session.

### Publishing the prompts

The eight troubleshooting prompts are **off by default** and published with:

```shell
export SUPPORT_PROMPTS=true
```

Setting it also appends a short instruction block telling the assistant to arm
support mode before troubleshooting, so an operator's own ad-hoc question is
covered and not only the eight prompts. That block is gated with the prompts
rather than shipped to everyone: it steers the model to withhold writes, and a
user who never opted into support mode should not find their writes latched off
and then need walking through the exit phrase.

The default is off because a published prompt appears in every user's prompt
menu the moment they upgrade. That makes publishing one a customer-facing
change, and it should be a deliberate decision rather than something inherited
from a version bump. It also means a prompt can be validated against real cases
before anyone outside a pilot can reach it.

`enter_support_mode` remains available under `SUPPORT_MODE` as well, where it is
a no-op reporting that the mode is already on. That is deliberate: it keeps a
prompt whose first instruction is "call `enter_support_mode`" coherent under
both paths, instead of having the model open every investigation by calling a
tool that is not there. `request_write_unlock` and `exit_support_mode` stay
withheld in that mode, since those are the two that could stand it down.

### Transport restriction

The three control tools refuse to run on `sse` and `streamable-http`. Soft mode
is per-process state, and an HTTP process can serve several clients, so one
client arming it would silently restrict every other client. On stdio there is
one process per client, which is what makes process state equal session state.
Use `SUPPORT_MODE` on the HTTP transports.

For the same reason, neither the prompts nor the arm-first instruction block is
published on those transports even with `SUPPORT_PROMPTS=true`. Publishing them
would hand the model an instruction whose first step cannot succeed, and the
prompts tell it to stop and report when arming errors.

### Session log

`exit_support_mode` returns every unlock granted and every write executed while
the mode was on:

```json
{
  "state": "off",
  "writes_executed": ["disconnect_sc_sidecar_binding"],
  "session_log": [
    {"action": "entered", "tool": null, "detail": "soft, armed by prompt"},
    {"action": "unlock_granted", "tool": "disconnect_sc_sidecar_binding",
     "detail": "operator authorized removing the stale binding"},
    {"action": "write_executed", "tool": "disconnect_sc_sidecar_binding"},
    {"action": "exited", "tool": null, "detail": "confirmed by typed phrase"}
  ]
}
```

That is the artifact worth attaching to a support ticket: it records what
changed and on whose authority, rather than leaving it to be reconstructed.

## Which tools are available

Every tool whose name begins with `get_`, `list_`, or `search_`, with one
deliberate exception in each direction. The authoritative list is
`SUPPORT_ALLOWED_TOOLS` in [`altr_mcp/modes.py`](../altr_mcp/modes.py).

**Excluded even though they are annotated `readOnlyHint`:**
`vault_detokenize`, `vault_partial_detokenize`, `critical_detokenize`,
`critical_partial_detokenize`. The annotation is correct, since detokenization
mutates nothing, but these return real customer values rather than
configuration. Support investigations do not need plaintext.

**Included even though they carry no annotation:** `search_audits`,
`search_query_audits`, `search_system_audits`. These are unannotated because
each POSTs a search request rather than issuing a GET. They change no governed
state, and no audit investigation is possible without them.

This is why support mode is not implemented as "allow anything with
`readOnlyHint`". The two sets differ by seven tools, and the difference matters
in both directions.

## Design notes

**It is an allow-list, not a deny-list.** A tool added in a future release is
unavailable in support mode until it is added to `SUPPORT_ALLOWED_TOOLS` on
purpose. A deny-list of the 85 withheld tools would expose anything new by
default, which is the wrong failure direction for a safety feature.

**Prompt arguments are framed as data, not instructions.** Every argument is
interpolated after the guardrail preamble, so text inside one is the most
recent thing the model read. The arguments are table names, roles, job IDs and
emails, pasted out of customer tickets, so each is delimited and the preamble
disclaims the delimited spans as data. Like the exit phrase, this is a
guardrail and not a boundary: it raises the cost of an injected "ignore the
above", it does not make it impossible.

**The allow-list is tested against the live registry.**
`tests/unit/test_support_mode.py` fails if a listed tool is no longer
registered, if an allowed tool is neither `readOnlyHint` nor one of the three
documented searches, if a `destructiveHint` tool appears in the list, or if the
detokenization exclusion is removed. When 11 tools were renamed from `delete_*`
to `disconnect_*` in 0.4.0, the stale names lived on in documented examples and
silently restricted nothing. These tests are there so the allow-list cannot rot
the same way.

**Mode is applied in `main()`, not at import.** The server instructions and the
`FastMCP` instance are built at module import, which happens before
`load_dotenv()` runs, so a `SUPPORT_MODE` value set in a `.env` file would not
be visible yet.

## Limitations

Support mode is a guardrail, not a security boundary. It runs in the server
process and is configured by whoever starts that process, so anyone who can set
`SUPPORT_MODE=true` can also unset it.

It is worth being precise about why that guardrail carries more weight here than
it would elsewhere: **there is no key-scoping control underneath it.** An ALTR
API key "inherits the full permissions of the administrator who creates it" and
"can't be scoped to a subset of permissions"
([Manage API keys](https://docs.altr.com/api/manage-api-keys/)), and only a
Super Administrator can create one, so every key this server authenticates with
holds full permissions by construction. There is also no read-only
administrator role to create a weaker key from: the roles are Administrator,
Super Administrator, and Data Consumer, and the last is limited to sidecar repo
users. So the usual advice, scope the credential and treat the application-level
mode as defence in depth, is not available. This mode is the control, not a
supplement to one.

What support mode does is make the safe path the default one, and make an unsafe
action require a deliberate act, a restart or a typed phrase, rather than a
slip.
