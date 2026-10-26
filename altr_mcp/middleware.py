"""Server middleware.

ToolRestrictionMiddleware hides and blocks tools listed in
RESTRICTED_TOOLS and, when an allow-list is in force, every tool absent
from it. ValidationRedactionMiddleware keeps rejected argument values out
of the error returned to the caller.

The allow-list can be static (passed in at construction, which is what
the SUPPORT_MODE env var does) or live (read from a
SupportModeController, which is what the enter_support_mode tool does).
Enforcement is the same code either way. That matters: the runtime path
is not a softer kind of check, it is the same check reading a value that
can change.
"""

from collections.abc import Set as AbstractSet
from typing import Iterable, Optional

import structlog
from fastmcp.exceptions import ToolError
from fastmcp.exceptions import ValidationError as FastMCPValidationError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import ValidationError

from altr_mcp.utils.logging import _validation_message

from altr_mcp.modes import parse_tool_list
from altr_mcp.support_control import SupportModeController

logger = structlog.get_logger(__name__)


class ToolRestrictionMiddleware(Middleware):
    """Hide restricted tools from tools/list and block them on tools/call.

    Filters, all applied:

    * ``restricted_tools`` is a deny-list from RESTRICTED_TOOLS. Named
      tools are withheld; everything else passes. This is the operator's
      list, so it wins over everything below it, including a granted
      unlock.
    * ``allowed_tools`` is an optional static allow-list. When supplied,
      only the named tools pass. This fails closed: a tool added in a
      future release is withheld until it is added to the allow-list on
      purpose.
    * ``controller``, when supplied, provides the allow-list live and
      may hold a one-shot unlock for a single named write.
    """

    def __init__(
        self,
        restricted_tools: Optional[str] = None,
        allowed_tools: Optional[Iterable[str]] = None,
        controller: Optional[SupportModeController] = None,
    ) -> None:
        self.restricted_tools: set[str] = parse_tool_list(restricted_tools)
        self.allowed_tools: Optional[set[str]] = (
            set(allowed_tools) if allowed_tools is not None else None
        )
        self.controller = controller
        self._checked_names = False
        if self.restricted_tools:
            logger.info(
                "tool_restriction_middleware.init",
                restricted_count=len(self.restricted_tools),
                restricted_tools=sorted(self.restricted_tools),
            )
        if self.allowed_tools is not None:
            logger.info(
                "tool_restriction_middleware.allow_list_active",
                allowed_count=len(self.allowed_tools),
            )

    def _effective_allow_list(self) -> Optional[AbstractSet[str]]:
        """The allow-list in force right now.

        A static list and a controller can both be present; the
        intersection applies, so neither can widen the other.
        """
        static = self.allowed_tools
        live = (
            self.controller.allowed_tools()
            if self.controller is not None
            else None
        )
        if static is None or live is None:
            return live if static is None else static
        return static & live

    def _withheld_reason(
        self, tool_name: str, allow: Optional[AbstractSet[str]]
    ) -> Optional[str]:
        """Return why a tool is unavailable, or None if it is available.

        Pure: safe to call from on_list_tools without spending an
        unlock.
        """
        if tool_name in self.restricted_tools:
            return "access restrictions"
        if allow is not None and tool_name not in allow:
            return "support read-only mode"
        return None

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        # No await from here down to consume_unlock() below. Requests are
        # dispatched concurrently (tg.start_soon in the low-level server),
        # and _withheld_reason() is what admits the call by reading
        # pending_unlock, so any yield point between that read and the
        # consume lets two parallel calls pass on one authorization.
        # test_two_concurrent_calls_spend_one_unlock_exactly_once covers it.
        reason = self._withheld_reason(
            tool_name, self._effective_allow_list()
        )
        if reason is not None:
            logger.warning(
                "tool_restriction_middleware.blocked",
                tool=tool_name,
                reason=reason,
            )
            raise ToolError(
                f"Tool '{tool_name}' is not available"
                f" due to {reason}"
            )
        # Spend any unlock for this tool, so its next call is blocked
        # again. See the no-await note above.
        if self.controller is not None:
            self.controller.consume_unlock(tool_name)
        return await call_next(context)

    def _check_names_once(self, registered: set[str]) -> None:
        """Warn about restricted names that match no registered tool.

        A name matching nothing restricts nothing, so a stale or misspelled
        entry silently leaves a tool exposed while the operator believes it is
        blocked. The 11 `delete_*` tools renamed to `disconnect_*` in 0.4.0 are
        the likely source.

        Deferred to the first tools/list rather than done in __init__ because
        this middleware holds no reference to the server and every FastMCP tool
        accessor is async, while main() is sync. Note the comparison set is the
        caller's visible tool list, which FastMCP has already filtered by
        enablement and per-session auth — not the raw registry.
        """
        if self._checked_names:
            return
        self._checked_names = True
        unknown = sorted(self.restricted_tools - registered)
        if unknown:
            logger.warning(
                "tool_restriction_middleware.unknown_tools",
                unknown_tools=unknown,
                unknown_count=len(unknown),
                hint=(
                    "these RESTRICTED_TOOLS entries match no registered tool"
                    " and restrict nothing; check for tools renamed in 0.4.0"
                ),
            )

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        all_tools = await call_next(context)
        allow = self._effective_allow_list()
        if not self.restricted_tools and allow is None:
            return all_tools
        self._check_names_once({t.name for t in all_tools})
        filtered = [
            t for t in all_tools
            if self._withheld_reason(t.name, allow) is None
        ]
        logger.debug(
            "tool_restriction_middleware.filtered",
            total=len(all_tools),
            visible=len(filtered),
        )
        return filtered


def _rejection_message(exc: Exception) -> str:
    """The field paths and messages of a rejected call, never its input."""
    # fastmcp 3.4.3+ wraps pydantic's error in its own and keeps it as __cause__.
    cause = exc if isinstance(exc, ValidationError) else exc.__cause__
    if isinstance(cause, ValidationError):
        return _validation_message(cause)
    return "invalid arguments"


class ValidationRedactionMiddleware(Middleware):
    """Replace argument-coercion errors with a message that carries no input.

    FastMCP coerces arguments before log_tool runs, and the pydantic error
    includes the rejected value. `from None` stops tracebacks rendering that error.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)
        except (ValidationError, FastMCPValidationError) as exc:
            message = _rejection_message(exc)
            logger.warning(
                "tool_argument_validation_failed",
                tool=context.message.name,
                error=message,
            )
            raise ToolError(f"Validation failed: {message}") from None
