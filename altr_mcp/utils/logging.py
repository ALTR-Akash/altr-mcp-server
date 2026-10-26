import functools
import json
import logging
import re
import sys
import uuid

import structlog
from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from altr_mcp.settings import get_settings

logger = structlog.get_logger(__name__)

# Safe default for an importer that never calls _configure_logging.
# structlog's default renderer prints frame locals, which hold tool arguments.
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(
            exception_formatter=structlog.dev.plain_traceback),
    ],
    # The default factory writes to stdout, which carries JSON-RPC under the
    # stdio transport. A log line on stdout corrupts the protocol.
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)


def _derive_action(func_name: str) -> str:
    """Strip CRUD prefix, replace underscores with spaces."""
    for prefix in ("get_", "create_", "delete_", "update_", "list_",
                   "add_", "connect_", "register_", "deregister_",
                   "trigger_", "approve_", "deny_", "cancel_", "search_"):
        if func_name.startswith(prefix):
            remainder = func_name[len(prefix):]
            return f"{prefix.rstrip('_')} {remainder.replace('_', ' ')}"
    return func_name.replace("_", " ")


# Redact credentials and user-supplied free text. Log identifiers, enums and
# cursors. Tokens stay readable on purpose, for reasons in docs/logging.md.
_REDACTED_ARGS = frozenset({
    # Plaintext being tokenized, and the free text that Shield's protect flow
    # takes. partial_detokenize mixes tokens and plaintext in `values`.
    "values", "text",
    # A DSN embeds its password inline: postgres://user:pw@host/db.
    "connection_string",
    # The suffix rule below covers `database_password` but not a bare
    # `password`, so the unprefixed forms are named outright.
    "password", "secret", "credentials", "passphrase", "private_key",
    "api_key", "auth_token", "access_key",
    # Human free text, where unannounced PII arrives. Redact it as for `text`.
    "comment", "comments", "attestation", "justification",
    # An audit search term is the data value someone hunts for. `filters` and
    # `filter_tree` carry the same term in report filters and DAM rule leaves.
    "statement_text_contains", "filters", "filter_tree",
})
# Matches any argument name, so a new parameter with one of these suffixes is
# covered. No `_token` suffix, because it would match the pagination cursors.
_REDACTED_SUFFIXES = ("_password", "_secret", "_credential", "_credentials",
                      "_private_key", "_passphrase")
_REDACTED = "<redacted>"


def _is_sensitive(name: str) -> bool:
    """Whether an argument's value must not be logged."""
    return name in _REDACTED_ARGS or name.endswith(_REDACTED_SUFFIXES)


def _redact(obj):
    """Replace sensitive values at every depth, and keep the dict keys.

    Truncation is no substitute, because secrets are short. Nested payloads can hold one.
    """
    if isinstance(obj, dict):
        return {
            key: _redact_value(value) if _is_sensitive(key) else _redact(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _redact_value(value):
    """Redact one value, keeping enough shape to debug with."""
    # Report an omitted argument as omitted. "<redacted>" would claim a secret
    # was sent, and a missing argument is a common cause of failures.
    if value is None or value == "":
        return value
    if isinstance(value, dict):
        return {name: _REDACTED for name in value}
    return _REDACTED


def _validation_message(exc: ValidationError) -> str:
    """Return field paths and messages, without the rejected values.

    Invariant: a validator must not put the rejected value in its ValueError
    text. For `value_error`, pydantic copies that text into msg.
    """
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) if parts else "validation failed"


def _format_kwargs(kwargs: dict) -> str:
    """Format kwargs for log line, truncating long values."""
    parts = []
    for k, v in kwargs.items():
        s = repr(v)
        if len(s) > 100:
            s = s[:97] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts) if parts else "no args"


def _summarize(result) -> str:
    """Extract a brief result summary for the completion log."""
    if isinstance(result, dict):
        # Handle {success, data, error} wrapper
        if "success" in result:
            if not result.get("success"):
                return f"error: {result.get('error', 'unknown')}"
            data = result.get("data")
            if isinstance(data, (list, dict)):
                return f"{len(data)} items"
            return "ok"
        return f"{len(result)} items"
    if isinstance(result, str):
        return f"{len(result)} chars"
    return "ok"


# pydantic renders `input_value=<repr>, input_type=<type>]`, and the caller
# controls the repr. Match greedily to the last ", input_type=", because the
# repr can contain "]" or that text. With no terminator, redact to line end.
# Not DOTALL, so the fallback loses one traceback line and keeps the frames.
_INPUT_VALUE = re.compile(r"input_value=.*(?=, input_type=)|input_value=.*")
# fastmcp 3.3+ logs pydantic's errors() list, where the value follows an
# `input` key. The value has no reliable end marker, so redact to line end.
_INPUT_KEY = re.compile(r"""(\\?(['"])input\\?\2\s*:).*""")


def _scrub_strings(obj):
    """Strip a rejected value out of every string in a nested structure."""
    if isinstance(obj, str):
        obj = _INPUT_VALUE.sub(f"input_value={_REDACTED}", obj)
        return _INPUT_KEY.sub(rf"\1 {_REDACTED}", obj)
    if isinstance(obj, dict):
        return {key: _REDACTED if key == "input" else _scrub_strings(value)
                for key, value in obj.items()}
    if isinstance(obj, list):
        return [_scrub_strings(item) for item in obj]
    return obj


def _scrub_rejected_values(logger, method_name, event_dict):
    """Remove rejected argument values before the renderer writes them.

    A logging.Filter cannot do this: the chain renders exception text later.
    """
    return _scrub_strings(event_dict)


# Libraries that set propagate=False on their own logger. _configure_logging
# reclaims them. fastmcp does this only at import, so one reclaim is enough.
_LIBRARY_LOGGERS = ("fastmcp",)

# httpx logs each request URL at INFO, query string included. search_audits
# puts statement_text_contains there. Silencing also covers future params.
_QUIET_LOGGERS = ("httpx",)


def _reclaim_library_loggers() -> None:
    """Route library output back through the root handler."""
    for name in _LIBRARY_LOGGERS:
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.propagate = True


def _own_debug_only(record: logging.LogRecord) -> bool:
    """Below INFO, pass only this server's records.

    Dependencies print raw requests and responses at DEBUG, which redaction cannot see.
    """
    return record.levelno >= logging.INFO or record.name.startswith("altr_mcp")


def _quiet_request_loggers(log_level: int) -> None:
    """Hold per-request dependency logging at WARNING or above."""
    # max() keeps a higher configured level. The child logger's level decides
    # whether a record exists, and root's handlers ignore root's own level.
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(max(log_level, logging.WARNING))


def _configure_logging(settings) -> None:
    """Render structlog and stdlib records through one handler.

    One formatter chain gives one place for the scrub processor and LOG_FORMAT.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Applied to records from both systems, so a dependency's line carries
    # the same level, timestamp and bound context as ours.
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        # Name the source logger, because one handler renders several libraries.
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.log_format.lower() == "json":
        renderer = structlog.processors.JSONRenderer()
        # Frame locals hold tool arguments. Set show_locals=False explicitly,
        # because the library default has changed before.
        exception_processor = structlog.processors.ExceptionRenderer(
            structlog.tracebacks.ExceptionDictTransformer(show_locals=False))
    else:
        renderer = structlog.dev.ConsoleRenderer(
            exception_formatter=structlog.dev.plain_traceback)
        exception_processor = structlog.processors.format_exc_info

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # A stdlib record gets foreign_pre_chain before rendering.
        # A structlog record has already had shared_processors.
        foreign_pre_chain=shared_processors + [exception_processor],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            exception_processor,
            # After the exception processor, so it sees rendered tracebacks.
            # Before the renderer, so it covers both output formats.
            _scrub_rejected_values,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(_own_debug_only)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
    _reclaim_library_loggers()
    _quiet_request_loggers(log_level)


def log_tool(func):
    """Decorator: correlation ID, structlog binding, invocation logging.

    On success: returns the tool's return value
    (expected: {success, data, error} dict).
    On ValidationError: logs tool_validation_error and
    raises ToolError with JSON error dict, which causes
    fastmcp to set isError: true in the MCP response.
    On general Exception: logs tool_failed and raises
    ToolError with JSON error dict.
    """
    action = _derive_action(func.__name__)

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        correlation_id = f"{func.__name__}:{uuid.uuid4().hex[:8]}"
        clear_contextvars()
        bind_contextvars(correlation_id=correlation_id)
        log = structlog.get_logger(__name__)

        # Dev mode: truncate args; JSON mode: full args. Redacted first in
        # both, since JSON mode does not truncate at all.
        settings = get_settings()
        safe_kwargs = _redact(kwargs)
        if settings.log_format.lower() == "json":
            kwargs_str = repr(safe_kwargs)
        else:
            kwargs_str = _format_kwargs(safe_kwargs)

        log.info("tool_invoked", action=action, args=kwargs_str)
        try:
            result = await func(*args, **kwargs)
            if result is None or result == "":
                log.warning("tool_no_results", action=action)
            else:
                log.info(
                    "tool_completed",
                    action=action,
                    summary=_summarize(result),
                )
            return result
        except ValidationError as e:
            error_msg = f"Validation failed: {_validation_message(e)}"
            log.warning(
                "tool_validation_error",
                action=action, error=error_msg)
            error_dict = {
                "success": False,
                "data": None,
                "error": error_msg,
            }
            # A chained __cause__ keeps the unredacted pydantic text reachable.
            # from None keeps the scrub processor a second guard, not the only one.
            raise ToolError(json.dumps(error_dict)) from None
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            log.error(
                "tool_failed",
                action=action,
                error=error_msg,
                exc_info=True,
            )
            error_dict = {
                "success": False,
                "data": None,
                "error": (
                    f"Failed to {action}: {error_msg}"
                ),
            }
            raise ToolError(json.dumps(error_dict)) from e
        finally:
            clear_contextvars()

    return wrapper
