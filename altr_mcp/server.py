import argparse
import sys
from pathlib import Path

from fastmcp import FastMCP
from pydantic import ValidationError

from altr_mcp import __version__
from altr_mcp.middleware import (
    ToolRestrictionMiddleware,
    ValidationRedactionMiddleware,
)
from altr_mcp.modes import SUPPORT_ALLOWED_TOOLS
from altr_mcp.settings import get_settings
from altr_mcp.support_control import MODE_ENTRY_TOOLS, get_controller
from altr_mcp.utils.logging import (
    _configure_logging,
    _validation_message,
)
from altr_mcp.prompts import register as register_prompts
from altr_mcp.tools import register_all

_INSTRUCTIONS = (
    Path(__file__).parent / "instructions.md"
).read_text(encoding="utf-8")
_SUPPORT_INSTRUCTIONS = (
    Path(__file__).parent / "instructions_support.md"
).read_text(encoding="utf-8")
_MODE_CONTROL_INSTRUCTIONS = (
    Path(__file__).parent / "instructions_mode_control.md"
).read_text(encoding="utf-8")
# version= is what clients see as serverInfo.version in the MCP handshake.
# Without it FastMCP reports its own version, not ours.
mcp = FastMCP("altr", instructions=_INSTRUCTIONS, version=__version__)
register_all(mcp)
# Prompts are registered in main(), not here, and only when
# SUPPORT_PROMPTS is set. Import time is too early to read it, since
# load_dotenv() has not run yet, and publishing a prompt puts it in
# every user's prompt menu on upgrade, so it needs to be opted into
# rather than inherited from a version bump.


def _parse_args(argv=None):
    """Handle --version/--help before any configuration is loaded.

    Both must work without ORG_ID/MAPI_* set: asking a program its version
    should never require credentials.
    """
    parser = argparse.ArgumentParser(
        prog="altr-mcp",
        description=(
            "MCP server for ALTR data security. Configuration is read from "
            "the environment; see the README for the full list."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"altr-mcp {__version__}",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Entry point. argv defaults to sys.argv[1:]; pass a list in tests."""
    _parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(override=True)
    try:
        settings = get_settings()
    except ValidationError as e:
        missing = [
            err["loc"][0]
            for err in e.errors()
            if err["type"] == "missing"
        ]
        if missing:
            fields = ", ".join(str(f).upper() for f in missing)
            print(
                f"ERROR: Missing required environment variables: {fields}",
                file=sys.stderr,
            )
        else:
            # _validation_message drops the rejected value. SecretStr masks only
            # the MAPI_* fields, so this call site must not rely on it.
            print(
                "ERROR: Configuration validation failed:\n"
                f"{_validation_message(e)}",
                file=sys.stderr,
            )
        sys.exit(1)
    _configure_logging(settings)

    # Support mode is applied here rather than at import time: the
    # instructions and the FastMCP instance are built when this module is
    # imported, which is before load_dotenv() above has had a chance to
    # populate SUPPORT_MODE from a .env file.
    #
    # The control tools refuse on the HTTP transports, where one process can
    # serve several clients and a per-process latch would restrict all of
    # them. Publishing an arming-first prompt or an arm-first instruction
    # there would tell the model to call something that cannot succeed.
    stdio = settings.mcp_transport == "stdio"

    # On the HTTP transports with support mode off, all three control
    # tools are still published and every call returns the transport
    # refusal. Hiding them needs a filter the middleware does not have (an
    # allow-list built with support mode off, or an explicit
    # unavailable-tools set with its own reason string), which is new
    # surface rather than a fix to this change.
    #
    # REVIEW-DEFERRED: control tools stay published on HTTP when support
    # mode is off; see the paragraph above for what a fix needs.
    allowed_tools = None
    if settings.support_mode:
        # Must match the controller's hard-mode list, because
        # _effective_allow_list() intersects the static list with the live
        # one: anything the controller adds and this omits gets stripped.
        # Omitting MODE_ENTRY_TOOLS blocked enter_support_mode in hard
        # mode, so every published prompt's first instruction failed in the
        # one configuration support engineers are told to run.
        #
        # Only on stdio, though. Arming refuses on the HTTP transports in
        # every state, so offering it there is a tool whose only possible
        # outcome is an error.
        allowed_tools = SUPPORT_ALLOWED_TOOLS | (
            MODE_ENTRY_TOOLS if stdio else frozenset()
        )
        mcp.instructions = f"{_INSTRUCTIONS}\n\n{_SUPPORT_INSTRUCTIONS}"

    if not settings.support_mode and settings.support_prompts and stdio:
        # Support mode is off but armable mid-session by enter_support_mode.
        # The model has to know that before it calls anything, and
        # instructions are only sent once, at initialize, so the hint cannot
        # be added later on demand.
        #
        # Gated behind SUPPORT_PROMPTS rather than shipped to everyone: this
        # block actively steers the model to latch the server read-only, so
        # an ordinary user who asked for a fix and never opted into support
        # mode should not have writes withheld and then need walking through
        # the exit phrase. Operators who opted into the prompts get it, and
        # it covers their ad-hoc questions too, not just the eight prompts.
        mcp.instructions = (
            f"{_INSTRUCTIONS}\n\n{_MODE_CONTROL_INSTRUCTIONS}"
        )

    # stdio only, hard mode included. Every prompt opens by calling
    # enter_support_mode, which refuses on the HTTP transports in every
    # state, so publishing them there hands the model an instruction whose
    # first step cannot succeed and which tells it to stop when it fails.
    if settings.support_prompts and stdio:
        register_prompts(mcp)

    # First call decides hard versus soft, so it has to happen after
    # settings are loaded and before any tool can reach the controller.
    controller = get_controller()

    # Register this first: FastMCP wraps in reverse order, so it is outermost
    # and redacts a ValidationError raised in any inner middleware.
    mcp.add_middleware(ValidationRedactionMiddleware())
    mcp.add_middleware(
        ToolRestrictionMiddleware(
            restricted_tools=settings.restricted_tools,
            allowed_tools=allowed_tools,
            controller=controller,
        )
    )

    # Build transport kwargs — host/port only for non-stdio transports
    kwargs: dict = {"transport": settings.mcp_transport}
    # fastmcp prints its startup banner as ASCII art on stderr. Under
    # LOG_FORMAT=json, it is the only output that is not JSON.
    if settings.log_format.lower() == "json":
        kwargs["show_banner"] = False
    if settings.mcp_transport in ("sse", "streamable-http"):
        kwargs["host"] = settings.mcp_host
        kwargs["port"] = settings.mcp_port
        # uvicorn runs dictConfig in Config(), after _configure_logging.
        # log_config=None keeps its loggers propagating to the one handler.
        kwargs["uvicorn_config"] = {"log_config": None}
    mcp.run(**kwargs)


if __name__ == "__main__":
    main()
