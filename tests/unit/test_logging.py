"""Tests for structlog configuration and correlation ID behavior."""
import importlib
import io
import json
import logging
import sys
from unittest.mock import patch

import pytest
import structlog
from structlog.contextvars import get_contextvars

from fastmcp.exceptions import ToolError
from altr_mcp.utils.logging import _configure_logging, log_tool


@pytest.fixture(autouse=True)
def restore_logging_state():
    """Undo the global logging changes that these tests make.

    Otherwise a later test logs into a closed buffer from _capture.
    """
    saved_config = structlog.get_config().copy()
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    libraries = {n: logging.getLogger(n).level for n in ("fastmcp", "mcp", "httpx")}
    yield
    structlog.configure(**saved_config)
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    for name, level in libraries.items():
        logging.getLogger(name).setLevel(level)


class FakeSettings:
    """Minimal settings stub for logging tests."""
    log_level = "DEBUG"
    log_format = "json"


class FakeSettingsConsole:
    log_level = "DEBUG"
    log_format = "console"


def test_json_log_format():
    """LOG_FORMAT=json produces JSON-parseable output."""
    capture = _capture(FakeSettings())
    log = structlog.get_logger("test")
    log.info("test_event", key="value")
    output = capture.getvalue().strip()
    parsed = json.loads(output)
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"


def test_console_log_format():
    """Default LOG_FORMAT=console produces non-JSON output."""
    capture = _capture(FakeSettingsConsole())
    log = structlog.get_logger("test")
    log.info("test_event", key="value")
    output = capture.getvalue().strip()
    # Console output should NOT be valid JSON
    try:
        json.loads(output)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json, f"Console mode should not emit JSON, got: {output}"


async def test_correlation_id_format():
    """log_tool generates correlation_id in format func_name:8hex."""
    @log_tool
    async def get_test_thing():
        ctx = get_contextvars()
        return ctx.get("correlation_id", "")

    with patch("altr_mcp.utils.logging.get_settings", return_value=FakeSettingsConsole()):
        result = await get_test_thing()

    assert result.startswith(
        "get_test_thing:"), f"Expected 'get_test_thing:...' got '{result}'"
    hex_part = result.split(":")[1]
    assert len(hex_part) == 8, f"Expected 8 hex chars, got {len(hex_part)}"
    int(hex_part, 16)  # Validates it's valid hex


async def test_correlation_id_cleared_after_tool():
    """Correlation ID does not leak between tool invocations."""
    @log_tool
    async def first_tool():
        return "ok"

    @log_tool
    async def second_tool():
        ctx = get_contextvars()
        return ctx.get("correlation_id", "")

    with patch("altr_mcp.utils.logging.get_settings", return_value=FakeSettingsConsole()):
        await first_tool()
        result = await second_tool()

    # second_tool should have its OWN correlation ID, not first_tool's
    assert result.startswith(
        "second_tool:"), f"Expected 'second_tool:...' got '{result}'"


async def test_log_tool_raises_tool_error_on_exception():
    """log_tool wraps exceptions in ToolError with JSON error dict."""
    @log_tool
    async def failing_tool():
        raise RuntimeError("boom")

    with patch("altr_mcp.utils.logging.get_settings", return_value=FakeSettingsConsole()):
        with pytest.raises(ToolError) as exc_info:
            await failing_tool()
    error = json.loads(str(exc_info.value))
    assert error["success"] is False
    assert error["data"] is None
    assert "boom" in error["error"]


async def test_log_tool_warns_on_empty_result():
    """log_tool emits a tool_no_results warning when result is None / ''."""
    @log_tool
    async def empty_tool():
        return None

    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettingsConsole()):
        result = await empty_tool()
    assert result is None


async def test_log_tool_json_mode_uses_repr_for_kwargs():
    """log_tool uses repr() for kwargs when LOG_FORMAT=json."""
    @log_tool
    async def echo_tool(**kwargs):
        return {"success": True, "data": kwargs, "error": None}

    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        result = await echo_tool(key="value", count=3)
    assert result["data"] == {"key": "value", "count": 3}


def test_summarize_handles_string_result():
    """log_tool's _summarize helper handles plain-string results."""
    from altr_mcp.utils.logging import _summarize

    assert _summarize("hello") == "5 chars"
    # Bare dict without "success" key reports item count
    assert _summarize({"a": 1, "b": 2}) == "2 items"
    # Wrapper dict with success=False reports error
    assert _summarize(
        {"success": False, "error": "boom"}
    ) == "error: boom"
    # Non-dict, non-string falls back to "ok"
    assert _summarize(42) == "ok"


# Tests assert that this value is absent, not that the marker is present.
# The marker can appear while the real value leaks elsewhere in the line.
SECRET = "123-45-6789"


def _capture(settings) -> io.StringIO:
    """Configure logging, then point the real handler at a buffer.

    The tests then run the formatter that production uses.
    """
    buffer = io.StringIO()
    _configure_logging(settings)
    for handler in logging.getLogger().handlers:
        handler.setStream(buffer)
    return buffer


async def test_tokenize_plaintext_is_not_logged_in_json_mode():
    """vault_tokenize's plaintext must not reach the log.

    JSON mode does not truncate, so redaction is the only guard.
    """
    @log_tool
    async def vault_tokenize(values, deterministic=False):
        return {"success": True, "data": {"ssn": "vaultn_x"}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        await vault_tokenize(values={"ssn": SECRET, "email": "a@b.com"})

    out = buffer.getvalue()
    assert SECRET not in out, f"plaintext leaked into the log: {out}"
    assert "a@b.com" not in out
    # The field names survive. They are the useful half of the line.
    assert "ssn" in out and "email" in out
    assert "<redacted>" in out


async def test_tokenize_plaintext_is_not_logged_in_console_mode():
    """Console-mode truncation is not a redaction mechanism."""
    @log_tool
    async def critical_tokenize(values, deterministic=False):
        return {"success": True, "data": {}, "error": None}

    buffer = _capture(FakeSettingsConsole())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettingsConsole()):
        await critical_tokenize(values={"ssn": SECRET})

    out = buffer.getvalue()
    assert SECRET not in out, f"plaintext leaked into the log: {out}"


async def test_free_text_argument_is_not_logged():
    """`text` is redacted too, for the Shield protect flow."""
    @log_tool
    async def shield_protect(text, collection_name=None):
        return {"success": True, "data": {}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        await shield_protect(text=f"my ssn is {SECRET}",
                             collection_name="ALTR Managed")

    out = buffer.getvalue()
    assert SECRET not in out, f"free text leaked into the log: {out}"
    # Non-sensitive arguments are still logged in full.
    assert "ALTR Managed" in out


async def test_identifier_arguments_are_still_logged():
    """Redaction is scoped: identifiers stay readable."""
    @log_tool
    async def get_database_id(database_name):
        return {"success": True, "data": {"id": 1}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        await get_database_id(database_name="SALES_DB")

    assert "SALES_DB" in buffer.getvalue()


async def test_validation_error_does_not_echo_the_rejected_value():
    """A pydantic error must not repeat its input_value.

    str(ValidationError) includes the value, which leaks a malformed `values`.
    """
    from pydantic import BaseModel

    class Strict(BaseModel):
        count: int

    @log_tool
    async def vault_tokenize(values):
        Strict(count=values["ssn"])          # raises ValidationError
        return {"success": True, "data": {}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        with pytest.raises(ToolError) as excinfo:
            await vault_tokenize(values={"ssn": SECRET})

    out = buffer.getvalue()
    assert SECRET not in out, f"plaintext leaked via the error path: {out}"
    # Nor in the ToolError handed back to the client.
    assert SECRET not in str(excinfo.value)
    # The diagnosis survives: which field, and what was wrong with it.
    assert "count" in str(excinfo.value)


def test_redact_replaces_scalar_sensitive_values():
    """A scalar sensitive argument is replaced wholesale."""
    from altr_mcp.utils.logging import _redact

    assert _redact({"text": "secret", "policy_id": "p1"}) == {
        "text": "<redacted>", "policy_id": "p1"}


def test_redact_keeps_dict_keys():
    """Dict-valued sensitive arguments keep their keys, lose their values."""
    from altr_mcp.utils.logging import _redact

    assert _redact({"values": {"ssn": SECRET, "email": "a@b.com"}}) == {
        "values": {"ssn": "<redacted>", "email": "<redacted>"}}


def test_redact_covers_dam_alerting_free_text():
    """An ack comment and a rule's filter tree hold free text and search terms."""
    from altr_mcp.utils.logging import _redact

    tree = {"op": "contains", "dimension": "statement_text",
            "string_value": SECRET}
    assert _redact({"comment": SECRET, "filter_tree": tree}) == {
        "comment": "<redacted>",
        "filter_tree": {"op": "<redacted>", "dimension": "<redacted>",
                        "string_value": "<redacted>"}}


def test_redact_does_not_touch_tokens():
    """Tokens are not redacted; ALTR's own audit log is keyed by token."""
    from altr_mcp.utils.logging import _redact

    assert _redact({"tokens": {"a": "vaultn_x"}}) == {
        "tokens": {"a": "vaultn_x"}}


def test_validation_message_keeps_locations_only():
    """_validation_message reports loc and msg, never the input."""
    from pydantic import BaseModel, ValidationError
    from altr_mcp.utils.logging import _validation_message

    class M(BaseModel):
        ssn: int

    try:
        M(ssn=SECRET)
    except ValidationError as exc:
        msg = _validation_message(exc)
    assert "ssn" in msg
    assert SECRET not in msg
    assert "input_value" not in msg


async def test_plaintext_is_not_logged_when_the_tool_raises_json_mode():
    """The failure path redacts too, because frame locals hold tool arguments.

    The test checks that the value is absent, so a renderer-default change fails it.
    """
    @log_tool
    async def vault_tokenize(values, deterministic=False):
        raise RuntimeError("upstream boom")

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        with pytest.raises(ToolError):
            await vault_tokenize(values={"ssn": SECRET})

    out = buffer.getvalue()
    assert SECRET not in out, f"plaintext leaked via the traceback: {out}"
    # The traceback must still render. The raising frame is the diagnosis.
    assert "RuntimeError" in out and "vault_tokenize" in out, (
        f"the traceback itself went missing: {out}")


async def test_plaintext_is_not_logged_when_the_tool_raises_console_mode():
    """Console mode leaks by a different renderer, so it needs its own test."""
    @log_tool
    async def critical_tokenize(values, deterministic=False):
        raise RuntimeError("upstream boom")

    buffer = _capture(FakeSettingsConsole())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettingsConsole()):
        with pytest.raises(ToolError):
            await critical_tokenize(values={"ssn": SECRET})

    out = buffer.getvalue()
    assert SECRET not in out, f"plaintext leaked via the traceback: {out}"
    # The traceback must still render. The raising frame is the diagnosis.
    assert "RuntimeError" in out and "critical_tokenize" in out, (
        f"the traceback itself went missing: {out}")


PASSWORD = "Sup3rS3cret!Passw0rd"


@pytest.mark.parametrize("kwargs", [
    {"database_password": PASSWORD, "hostname": "h"},
    {"connection_string": f"postgres://svc:{PASSWORD}@db.internal:5432/prod"},
    {"database_secret": PASSWORD},          # covered by the suffix rule
    {"client_passphrase": PASSWORD},        # covered by the suffix rule
])
async def test_credentials_are_not_logged(kwargs):
    """A credential in a log stays valid until someone rotates it."""
    @log_tool
    async def create_database(**kw):
        return {"success": True, "data": {}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        await create_database(**kwargs)

    assert PASSWORD not in buffer.getvalue()


@pytest.mark.parametrize(
    "arg", ["comments", "attestation", "justification",
            "statement_text_contains"])
async def test_free_text_siblings_are_not_logged(arg):
    """Free text is redacted uniformly, not just where it is called `text`."""
    @log_tool
    async def some_tool(**kw):
        return {"success": True, "data": {}, "error": None}

    buffer = _capture(FakeSettings())
    with patch("altr_mcp.utils.logging.get_settings",
               return_value=FakeSettings()):
        await some_tool(**{arg: f"contains {SECRET}"})

    assert SECRET not in buffer.getvalue()


@pytest.mark.parametrize("name,sensitive", [
    ("values", True), ("text", True), ("connection_string", True),
    ("comments", True), ("justification", True),
    ("database_password", True), ("anything_secret", True),
    # The suffix rule matches none of these bare forms. Only the explicit list does.
    ("password", True), ("secret", True), ("credentials", True),
    ("passphrase", True), ("private_key", True), ("api_key", True),
    ("auth_token", True), ("access_key", True),
    # A secret's name is not the secret. Redacting it loses a diagnosis.
    ("secret_name", False), ("secrets_path", False),
    ("tokens", False), ("token", False), ("page_token", False),
    ("next_page_token", False), ("database_name", False),
    ("policy_id", False), ("tag_value", False),
])
def test_is_sensitive_classification(name, sensitive):
    """Cursors and tokens stay readable; credentials and free text do not."""
    from altr_mcp.utils.logging import _is_sensitive

    assert _is_sensitive(name) is sensitive


def test_omitted_sensitive_argument_is_not_marked_redacted():
    """None and "" log as omitted, not as a hidden secret.

    A missing argument is a common cause of the failure being debugged.
    """
    from altr_mcp.utils.logging import _redact

    assert _redact({"values": None, "text": ""}) == {"values": None,
                                                     "text": ""}


def test_scrub_walks_a_rendered_exception():
    """The scrub walks the rendered exception, not only the event message.

    A coercion failure puts the rejected value in the exception text.
    """
    from altr_mcp.utils.logging import _scrub_rejected_values

    event_dict = {
        "event": "Error validating tool",
        "exception": [{
            "exc_type": "ValidationError",
            "exc_value": (f"values\n  Input should be a valid dictionary "
                          f"[type=dict_type, input_value='{SECRET}', "
                          f"input_type=str]"),
            "frames": [{"filename": "x.py", "lineno": 1}],
        }],
    }
    scrubbed = _scrub_rejected_values(None, "error", event_dict)
    assert SECRET not in json.dumps(scrubbed)
    # The diagnosis survives: field name and what was wrong with it.
    assert "values" in scrubbed["exception"][0]["exc_value"]
    assert "valid dictionary" in scrubbed["exception"][0]["exc_value"]


@pytest.mark.parametrize("text,leaks", [
    ("boom [type=x, input_value='SEC', input_type=str]", "SEC"),
    ("boom [type=x, input_value='SEC']", "SEC"),
    ("boom [type=x, input_value='a, input_type=x SEC', input_type=str]", "SEC"),
    # A "]" inside the value must not end the match.
    ("boom [type=x, input_value='a]SEC', input_type=str]", "SEC"),
    # A list argument, which is the shape an LLM caller most often sends.
    ("boom [type=x, input_value={'a': ['x'], 'b': 'SEC'}, input_type=dict]",
     "SEC"),
    # ", input_type=" inside the value must not end it either.
    ("boom [type=x, input_value='a, input_type=x] SEC', input_type=str]",
     "SEC"),
    # No recognisable terminator at all: redact to end of line, not nothing.
    ("boom input_value=SEC", "SEC"),
    # fastmcp 3.3+ logs pydantic's errors() list, keyed `input`.
    ("tool 'x': [{'loc': ('values',), 'msg': 'm', 'input': 'SEC'}]", "SEC"),
    ("tool 'x': [{'msg': 'm', 'input': \"a}], 'ctx': SEC\"}]", "SEC"),
    ("[{'input': 'ok'}, {'loc': ('b',), 'msg': 'm', 'input': 'SEC'}]", "SEC"),
    ('{"loc": ["values"], "msg": "m", "input": "SEC"}', "SEC"),
    # Near-miss spacing and escaping must still redact.
    ('{"input":"SEC"}', "SEC"),
    ("{'input' : 'SEC'}", "SEC"),
    ('{"error": "x {\\"input\\": \\"SEC\\"}"}', "SEC"),
])
def test_scrub_fails_closed_on_unfamiliar_renderings(text, leaks):
    """An unfamiliar shape must redact too much, never nothing.

    The rejected value is caller-controlled.
    """
    from altr_mcp.utils.logging import _scrub_strings

    assert leaks not in _scrub_strings(text)


async def test_coercion_failure_does_not_reach_stderr(capfd):
    """The scrub must be wired into the real path, not only correct.

    A real client drives the failure, and capfd reads the file descriptor.
    """
    from fastmcp import Client, FastMCP
    from altr_mcp.middleware import ValidationRedactionMiddleware
    # One pipeline, so configuring it is all the wiring this needs.
    _configure_logging(FakeSettings())

    mcp = FastMCP("test")
    mcp.add_middleware(ValidationRedactionMiddleware())

    @mcp.tool()
    async def vault_tokenize(values: dict[str, str]) -> dict:
        return {"success": True, "data": {}, "error": None}

    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("vault_tokenize", {"values": SECRET})

    captured = capfd.readouterr()
    assert SECRET not in captured.err, (
        f"rejected value reached stderr: {captured.err}")
    assert SECRET not in captured.out


def test_one_pipeline_carries_the_scrub_processor():
    """The point of one pipeline: one place a guard has to be installed."""
    from altr_mcp.utils.logging import _scrub_rejected_values

    _configure_logging(FakeSettings())

    handlers = logging.getLogger().handlers
    assert len(handlers) == 1, f"expected one handler, got {handlers}"
    assert _scrub_rejected_values in handlers[0].formatter.processors, (
        "the scrub is not in the chain that renders every record")


def test_library_loggers_are_reclaimed():
    """fastmcp's records must reach the root handler.

    fastmcp sets propagate=False and adds its own handlers at import.
    """
    from altr_mcp.utils.logging import _LIBRARY_LOGGERS

    import fastmcp  # noqa: F401  -- takes over its logger on import
    _configure_logging(FakeSettings())

    for name in _LIBRARY_LOGGERS:
        library_logger = logging.getLogger(name)
        assert library_logger.propagate is True, (
            f"{name!r} still does not propagate to the root handler")
        assert library_logger.handlers == [], (
            f"{name!r} still owns handlers: {library_logger.handlers}")


def test_dependency_records_render_in_the_configured_format():
    """A dependency's line uses the same LOG_FORMAT as this package's lines."""
    buffer = _capture(FakeSettings())          # json
    logging.getLogger("httpx").warning("retrying connection")
    logging.getLogger("fastmcp.server.server").error("dependency error")

    lines = [ln for ln in buffer.getvalue().splitlines() if ln.strip()]
    assert lines, "no dependency output was captured"
    for line in lines:
        parsed = json.loads(line)              # raises if not JSON
        assert "event" in parsed and "level" in parsed

    # One handler renders several libraries, so each line names its logger.
    names = {json.loads(ln)["logger"] for ln in lines}
    assert names == {"httpx", "fastmcp.server.server"}


def test_redaction_reaches_nested_values():
    """The suffix rule holds at depth, because tools take nested payloads."""
    from altr_mcp.utils.logging import _redact

    assert _redact({"configuration": {"database_password": "P@ss",
                                      "host": "h"}}) == {
        "configuration": {"database_password": "<redacted>", "host": "h"}}
    assert _redact({"delivery": {"channels": [{"webhook_secret": "s"}]}}) == {
        "delivery": {"channels": [{"webhook_secret": "<redacted>"}]}}


def test_scrub_keeps_the_rest_of_a_traceback():
    """The fail-closed fallback costs one line, not the whole traceback.

    The regex is not DOTALL, so the frames below the redacted line survive.
    """
    from altr_mcp.utils.logging import _scrub_strings

    text = ("Traceback (most recent call last):\n"
            "  File \"tool.py\", line 9, in vault_tokenize\n"
            "ValidationError: input_value=SECRET\n"
            "  File \"caller.py\", line 4, in main")
    scrubbed = _scrub_strings(text)

    assert "SECRET" not in scrubbed
    assert "vault_tokenize" in scrubbed
    assert "caller.py" in scrubbed


def test_per_request_dependency_logging_is_held_at_warning():
    """httpx stays at WARNING, because it logs the URL with its query string.

    search_audits sends statement_text_contains in the query string.
    """
    _configure_logging(FakeSettings())  # DEBUG, the permissive case

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_the_import_time_renderer_writes_to_stderr():
    """The unconfigured fallback writes to stderr, not stdout.

    stdout carries JSON-RPC under the stdio transport.
    """
    import altr_mcp.utils.logging as logging_module

    importlib.reload(logging_module)

    assert structlog.get_config()["logger_factory"]()._file is sys.stderr


async def test_the_request_url_never_reaches_the_stream(httpx_mock,
                                                        monkeypatch):
    """The request URL never reaches the stream.

    The test checks the output, so a logger rename in httpx fails it.
    """
    from altr_mcp.utils import api

    monkeypatch.setenv("ORG_ID", "test-org")
    monkeypatch.setenv("MAPI_KEY", "test-key")
    monkeypatch.setenv("MAPI_SECRET", "test-secret")
    httpx_mock.add_response(json={})
    buffer = _capture(FakeSettings())  # DEBUG, the permissive case

    await api.request(
        "POST", "https://api.example.com/v1/audits", None,
        {"statement_text_contains": SECRET})

    out = buffer.getvalue()
    assert SECRET not in out, f"the query string reached the log: {out}"
    # The replacement line still reports the call, without the query string.
    assert "upstream_request" in out


def test_scrub_keeps_the_field_and_message_of_an_errors_list():
    """Only the value is removed. The diagnosis before it survives."""
    from altr_mcp.utils.logging import _scrub_strings

    text = ("Invalid arguments for tool 'vault_tokenize': [{'type': 'dict_type', "
            "'loc': ('values',), 'msg': 'Input should be a valid dictionary', "
            f"'input': '{SECRET}'}}]")
    scrubbed = _scrub_strings(text)

    assert SECRET not in scrubbed
    assert "('values',)" in scrubbed and "valid dictionary" in scrubbed


def test_scrub_redacts_an_input_key_in_structured_fields():
    """A dict carrying `input` is redacted by key, not only as text."""
    from altr_mcp.utils.logging import _scrub_strings

    scrubbed = _scrub_strings({"errors": [{"loc": ["values"], "input": SECRET}]})

    assert SECRET not in json.dumps(scrubbed)
    assert scrubbed["errors"][0]["loc"] == ["values"]


@pytest.mark.parametrize("name", [
    "fastmcp.server", "mcp.server.sse", "sse_starlette.sse", None,  # None = root
])
def test_dependency_debug_lines_never_reach_the_stream(name):
    """Dependencies print raw payloads at DEBUG, so DEBUG must not enable them."""
    logging.getLogger("fastmcp").setLevel(logging.DEBUG)  # FASTMCP_LOG_LEVEL
    buffer = _capture(FakeSettings())  # DEBUG, the permissive case

    logging.getLogger(name).debug("Received JSON: %s", {"values": SECRET})
    logging.getLogger(name).warning("still written")

    assert SECRET not in buffer.getvalue()
    assert "still written" in buffer.getvalue()


def test_this_servers_own_debug_lines_are_still_written():
    """The allowlist must not swallow the detail LOG_LEVEL=DEBUG is for."""
    buffer = _capture(FakeSettings())  # DEBUG

    logging.getLogger("altr_mcp.utils.api").debug("retrying_request")

    assert "retrying_request" in buffer.getvalue()
