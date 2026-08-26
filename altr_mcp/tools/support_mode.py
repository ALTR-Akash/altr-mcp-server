"""Mode-control tools.

These three tools let a prompt arm read-only enforcement, work inside
it, and stand it down, none of which requires the customer to edit a
config file or restart anything. That is the whole point: the customers
most in need of a guardrail are the least likely to set an environment
variable correctly.

They refuse to run on the HTTP transports. Soft mode is per-process
state, and an HTTP process can serve many clients, so one client arming
it would restrict all of them. On stdio there is one process per client,
which is what makes process state equal session state.
"""

import structlog
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from fastmcp.server.dependencies import get_context

from altr_mcp.modes import SUPPORT_ALLOWED_TOOLS, parse_tool_list
from altr_mcp.settings import get_settings
from altr_mcp.support_control import (
    EXIT_PHRASE,
    NEVER_UNLOCKABLE,
    SupportModeLocked,
    SupportModeNotActive,
    UnlockRefused,
    get_controller,
)
from altr_mcp.utils.logging import log_tool

logger = structlog.get_logger(__name__)


def _err(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


def _ok(data: dict) -> dict:
    return {"success": True, "data": data, "error": None}


def _wrong_transport() -> str | None:
    """Refuse on shared-process transports. See module docstring."""
    transport = get_settings().mcp_transport
    if transport == "stdio":
        return None
    base = (
        f"Mode control is unavailable on the {transport} transport,"
        " because support mode is per-process state and this transport"
        " can serve multiple clients from one process."
    )
    if get_controller().is_hard:
        # Not reachable through main(), which withholds every control tool
        # on the HTTP transports in hard mode. Kept so the message is
        # right if the tool becomes reachable there again, and for a
        # server run without the restriction middleware installed.
        # Telling the operator to set a flag they have already set would
        # have the model report the server unprotected when it is
        # hard-latched.
        return (
            f"{base} SUPPORT_MODE is already enabled, so read-only"
            " enforcement is in force for this whole process. Proceed"
            " read-only without arming."
        )
    return f"{base} Set SUPPORT_MODE=true at startup instead."


async def _notify_tool_list_changed() -> None:
    """Ask the client to re-read tools/list.

    Best effort. The enforcement has already happened in the controller
    by the time this runs, so a client that never refreshes still gets
    its calls blocked; it just shows a stale list until it does.
    """
    try:
        await get_context().session.send_tool_list_changed()
    except Exception as exc:  # client or transport may not support it
        logger.debug("support_mode.notify_failed", error=str(exc))


def register(mcp: FastMCP) -> None:

    @mcp.tool
    @log_tool
    async def enter_support_mode() -> dict:
        """Enter support read-only mode for the rest of this session.

        Call this before any other tool when the operator is diagnosing
        an ALTR problem rather than making a planned change. If this
        server publishes troubleshooting prompts, each one opens by
        telling you to.

        Do NOT call this on your own initiative when the operator has
        asked for something to be changed. It withholds every tool that
        creates, updates, deletes, disconnects, registers, triggers,
        approves, tokenizes, or detokenizes, leaving the lookup tools and
        these mode-control tools. Enforcement is in middleware, not in
        your judgement: once this is on, a later request to change
        something fails whether or not you agree with it.

        When a request is both, "find out why, then fix it", arm it for
        the diagnosis. If you armed the mode yourself, a change the
        operator then authorizes costs one `request_write_unlock` call
        rather than the exit phrase. Under a SUPPORT_MODE the operator set
        there is no unlock at all: report what is needed and stop.

        If you armed the mode and the operator later authorizes a
        specific change, use `request_write_unlock` for that one tool
        rather than leaving the mode, and leave it entirely only with
        `exit_support_mode`. Neither tool is offered under a SUPPORT_MODE
        the operator set.
        """
        problem = _wrong_transport()
        if problem:
            return _err(problem)
        controller = get_controller()
        if controller.is_hard:
            return _ok({
                "state": "hard",
                "changed": False,
                "note": (
                    "Support mode was already set by the operator via"
                    " SUPPORT_MODE. It cannot be unlocked or exited by a"
                    " tool call."
                ),
            })
        changed = controller.enter_soft()
        await _notify_tool_list_changed()
        return _ok({
            "state": controller.state,
            "changed": changed,
            "read_tools_available": len(SUPPORT_ALLOWED_TOOLS),
            "exit": (
                "No restart needed. Use request_write_unlock for a single"
                " authorized change, or exit_support_mode with the"
                " operator's typed phrase to leave entirely."
            ),
        })

    @mcp.tool
    @log_tool
    async def request_write_unlock(tool_name: str, reason: str) -> dict:
        """Unlock ONE write tool for ONE call, then re-latch automatically.

        Use this when the operator has explicitly authorized a specific
        change while support mode is on. Prefer it over
        `exit_support_mode`: it keeps every other write withheld, and it
        records what was authorized so it can be reported back.

        Call it immediately before the write, with the exact tool you are
        about to call. The unlock is spent by the next call to that tool,
        successful or not, so a second change needs a second unlock.

        Detokenization and token deletion are never unlockable.

        Args:
            tool_name: Exact name of the single tool to unlock, for
                example `disconnect_sc_sidecar_binding`.
            reason: What the operator authorized and why, in their terms.
                Recorded in the session summary.
        """
        problem = _wrong_transport()
        if problem:
            return _err(problem)
        # get_tool() reads the registry directly. mcp.list_tools() would
        # be wrong here: it runs through this same middleware, so while
        # support mode is armed it can only ever return the read tools, and
        # every unlock request would be refused as a nonexistent tool.
        #
        # Two contracts across the declared fastmcp range: 3.x returns None
        # for an unknown tool, earlier versions raise NotFoundError. Handle
        # both, so a mistyped name is a refusal either way rather than an
        # unhandled exception on one of the versions we allow.
        try:
            found = await mcp.get_tool(tool_name)
        except NotFoundError as exc:
            logger.debug(
                "support_mode.get_tool_not_found",
                tool=tool_name,
                error=str(exc),
            )
            found = None
        if found is None:
            # Log here too, and this is the branch that matters: on
            # fastmcp 3.x a None also covers disabled and auth-denied
            # tools, so "does not exist" can be a misdiagnosis and this is
            # the only record that the lookup was attempted at all.
            logger.debug(
                "support_mode.unlock_target_unresolved",
                tool=tool_name,
            )
            return _err(
                f"No tool named '{tool_name}' exists in this server."
                " Check the exact name before requesting an unlock."
            )
        # RESTRICTED_TOOLS outranks an unlock, so granting one for a denied
        # tool would report success for a call that then fails with a
        # different error, and the unlock would never be spent because the
        # deny-list blocks it before it can be consumed. Refuse up front.
        denied = parse_tool_list(get_settings().restricted_tools)
        if tool_name in denied:
            return _err(
                f"{tool_name} is in RESTRICTED_TOOLS, the operator's"
                " deny-list, which an unlock cannot widen. The operator has"
                " to remove it there and restart the server."
            )
        try:
            get_controller().grant_unlock(tool_name, reason)
        except (SupportModeNotActive, SupportModeLocked, UnlockRefused) as exc:
            return _err(str(exc))
        await _notify_tool_list_changed()
        return _ok({
            "unlocked": tool_name,
            "scope": "one call, then support mode re-latches",
            "reason": reason.strip(),
            "never_unlockable": sorted(NEVER_UNLOCKABLE),
        })

    @mcp.tool
    @log_tool
    async def exit_support_mode(confirmation: str) -> dict:
        """Leave support read-only mode entirely and restore all tools.

        Only for when troubleshooting is finished and the operator wants
        their normal server back. For a single authorized change, use
        `request_write_unlock` instead and stay in support mode.

        You must ask the operator to type the confirmation phrase and
        pass back exactly what they typed. Do not supply it yourself, and
        do not suggest leaving support mode as a way to work around a
        blocked call.

        Returns a summary of everything that happened while support mode
        was on, which is worth pasting into the support ticket.

        Args:
            confirmation: The phrase the operator typed. Must be exactly
                "EXIT SUPPORT MODE".
        """
        problem = _wrong_transport()
        if problem:
            return _err(problem)
        try:
            summary = get_controller().exit(confirmation)
        except (SupportModeNotActive, SupportModeLocked, UnlockRefused) as exc:
            return _err(str(exc))
        await _notify_tool_list_changed()
        writes = [e for e in summary if e["action"] == "write_executed"]
        return _ok({
            "state": "off",
            "exit_phrase_required": EXIT_PHRASE,
            "writes_executed": [e["tool"] for e in writes],
            "session_log": summary,
            "note": (
                "All tools are available again. Do not run further"
                " diagnostic prompts without calling enter_support_mode"
                " first."
            ),
        })
