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
# main() registers the prompts: SUPPORT_PROMPTS is unset until
# load_dotenv() runs.


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

    # Applied here, not at import, so SUPPORT_MODE from .env is visible.
    # Control tools refuse on HTTP, so prompts and arming hints need stdio.
    stdio = settings.mcp_transport == "stdio"

    # REVIEW-DEFERRED: with support mode off, HTTP still lists the control
    # tools and each call refuses. Hiding them needs a new middleware filter.
    allowed_tools = None
    if settings.support_mode:
        # The middleware intersects this with the controller's list. Add
        # MODE_ENTRY_TOOLS on stdio, or hard mode loses enter_support_mode.
        allowed_tools = SUPPORT_ALLOWED_TOOLS | (
            MODE_ENTRY_TOOLS if stdio else frozenset()
        )
        mcp.instructions = f"{_INSTRUCTIONS}\n\n{_SUPPORT_INSTRUCTIONS}"

    elif settings.support_prompts and stdio:
        # Instructions go out once, at initialize, so the arming hint ships
        # now. It steers the model to withhold writes, so only opt-ins get it.
        mcp.instructions = (
            f"{_INSTRUCTIONS}\n\n{_MODE_CONTROL_INSTRUCTIONS}"
        )

    # stdio only, hard mode included: every prompt opens with
    # enter_support_mode, which refuses on HTTP in every state.
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
