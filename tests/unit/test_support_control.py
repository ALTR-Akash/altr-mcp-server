"""Unit tests for runtime support mode.

The load-bearing claims, and why each is tested:

* A prompt-armed latch is enforced in middleware, not by the model, so a
  write attempted on a later turn is blocked.
* An operator-set latch cannot be stood down by any tool. If this
  regresses, SUPPORT_MODE stops being a guarantee and becomes a default.
* An unlock covers one call to one named tool and is spent even when
  that call fails, so it cannot become a standing write permission.
* Detokenization is never unlockable at any scope.
* RESTRICTED_TOOLS outranks an unlock, so the operator's deny-list
  cannot be widened from inside the session.
"""
import pytest
from fastmcp.exceptions import ToolError
from unittest.mock import AsyncMock, MagicMock

from altr_mcp.middleware import ToolRestrictionMiddleware
from altr_mcp.modes import DISCLOSURE_TOOLS, SUPPORT_ALLOWED_TOOLS
from altr_mcp.support_control import (
    CONTROL_TOOLS,
    EXIT_PHRASE,
    MODE_ENTRY_TOOLS,
    MODE_STANDDOWN_TOOLS,
    NEVER_UNLOCKABLE,
    SupportModeController,
    SupportModeLocked,
    SupportModeNotActive,
    UnlockRefused,
)


def _ctx(tool_name):
    context = MagicMock()
    context.message.name = tool_name
    return context


def _tool(name):
    t = MagicMock()
    t.name = name
    return t


# ── state machine ───────────────────────────────────────────────────────

def test_starts_off_and_allows_everything():
    c = SupportModeController()
    assert c.state == "off"
    assert c.allowed_tools() is None


def test_enter_soft_arms_the_allow_list():
    c = SupportModeController()
    assert c.enter_soft() is True
    assert c.state == "soft"
    allowed = c.allowed_tools()
    assert "get_tags" in allowed
    assert "disconnect_database" not in allowed


def test_enter_soft_is_idempotent():
    c = SupportModeController()
    c.enter_soft()
    assert c.enter_soft() is False


def test_soft_mode_exposes_the_control_tools():
    """A customer who armed it has to be able to work inside it."""
    c = SupportModeController()
    c.enter_soft()
    assert CONTROL_TOOLS <= c.allowed_tools()


def test_hard_mode_withholds_only_the_standdown_tools():
    """The whole point of the hard path: no tool can stand it down.

    Arming stays reachable, because it can only be a no-op there and
    because every published prompt opens by calling it. Withholding it
    would make each prompt start by naming a tool that does not exist.
    """
    c = SupportModeController(hard=True)
    assert c.state == "hard"
    assert MODE_ENTRY_TOOLS <= c.allowed_tools()
    assert not (MODE_STANDDOWN_TOOLS & c.allowed_tools())


def test_arming_in_hard_mode_cannot_loosen_anything():
    """enter_support_mode is reachable in hard mode, so prove it is inert."""
    c = SupportModeController(hard=True)
    before = c.allowed_tools()
    assert c.enter_soft() is False
    assert c.state == "hard"
    assert c.allowed_tools() == before


# ── the hard path is not reversible by tools ────────────────────────────

def test_hard_mode_cannot_be_exited():
    c = SupportModeController(hard=True)
    with pytest.raises(SupportModeLocked):
        c.exit(EXIT_PHRASE)
    assert c.state == "hard"


def test_hard_mode_cannot_grant_an_unlock():
    c = SupportModeController(hard=True)
    with pytest.raises(SupportModeLocked):
        c.grant_unlock("disconnect_database", "operator said so")
    assert c.pending_unlock is None


# ── exit requires the typed phrase ──────────────────────────────────────

def test_exit_refuses_without_the_exact_phrase():
    c = SupportModeController()
    c.enter_soft()
    for attempt in ("", "exit support mode", "EXIT SUPPORT MODE ", "yes"):
        with pytest.raises(UnlockRefused):
            c.exit(attempt)
        assert c.state == "soft"


def test_exit_with_phrase_restores_everything_and_returns_log():
    c = SupportModeController()
    c.enter_soft()
    c.grant_unlock("update_rule", "operator approved the rule fix")
    c.consume_unlock("update_rule")
    summary = c.exit(EXIT_PHRASE)
    assert c.state == "off"
    assert c.allowed_tools() is None
    actions = [e["action"] for e in summary]
    assert actions == [
        "entered", "unlock_granted", "write_executed", "exited",
    ]
    assert summary[2]["tool"] == "update_rule"


def test_a_second_cycle_reports_only_its_own_activity():
    """The summary is pasted into a support ticket, so stale writes
    over-report what that session actually authorized."""
    c = SupportModeController()
    c.enter_soft()
    c.grant_unlock("delete_rule", "first cycle")
    c.consume_unlock("delete_rule")
    first = c.exit(EXIT_PHRASE)
    assert [
        e["tool"] for e in first if e["action"] == "write_executed"
    ] == ["delete_rule"]

    c.enter_soft()
    second = c.exit(EXIT_PHRASE)

    assert [e["action"] for e in second] == ["entered", "exited"]
    assert not [e for e in second if e["action"] == "write_executed"]


def test_exit_when_off_is_an_error_not_a_silent_success():
    c = SupportModeController()
    with pytest.raises(SupportModeNotActive):
        c.exit(EXIT_PHRASE)


# ── unlock scope ────────────────────────────────────────────────────────

def test_unlock_needs_a_reason():
    c = SupportModeController()
    c.enter_soft()
    for reason in ("", "   "):
        with pytest.raises(UnlockRefused):
            c.grant_unlock("update_rule", reason)


def test_unlock_refuses_tools_that_are_already_available():
    c = SupportModeController()
    c.enter_soft()
    with pytest.raises(UnlockRefused):
        c.grant_unlock("get_tags", "no unlock needed")


@pytest.mark.parametrize("tool_name", sorted(NEVER_UNLOCKABLE))
def test_detokenization_and_token_deletes_are_never_unlockable(tool_name):
    """No scope is narrow enough to justify handing back plaintext."""
    c = SupportModeController()
    c.enter_soft()
    with pytest.raises(UnlockRefused):
        c.grant_unlock(tool_name, "customer really wants to see the value")
    assert c.pending_unlock is None


def test_never_unlockable_covers_every_disclosure_tool():
    assert DISCLOSURE_TOOLS <= NEVER_UNLOCKABLE


def test_unlock_is_spent_by_one_consume():
    c = SupportModeController()
    c.enter_soft()
    c.grant_unlock("update_rule", "authorized")
    assert c.consume_unlock("update_rule") is True
    assert c.consume_unlock("update_rule") is False
    assert c.pending_unlock is None


def test_unlock_does_not_cover_a_different_tool():
    c = SupportModeController()
    c.enter_soft()
    c.grant_unlock("update_rule", "authorized")
    assert c.consume_unlock("delete_rule") is False
    # ...and the original unlock is still intact, not silently burned.
    assert c.pending_unlock == "update_rule"


def test_only_one_unlock_is_pending_at_a_time():
    c = SupportModeController()
    c.enter_soft()
    c.grant_unlock("update_rule", "first")
    c.grant_unlock("update_tag", "second")
    assert c.pending_unlock == "update_tag"
    assert c.consume_unlock("update_rule") is False


# ── middleware integration ──────────────────────────────────────────────

async def test_soft_latch_blocks_a_write_on_a_later_turn():
    """The failure this whole feature exists to stop."""
    c = SupportModeController()
    m = ToolRestrictionMiddleware(controller=c)

    # Turn one: nothing armed, everything passes.
    assert await m.on_call_tool(
        _ctx("disconnect_database"), AsyncMock(return_value="ok")
    ) == "ok"

    # The prompt arms it.
    c.enter_soft()

    # Turn two, "just delete it anyway", now fails in middleware.
    call_next = AsyncMock()
    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(_ctx("disconnect_database"), call_next)
    call_next.assert_not_called()


async def test_unlocked_tool_passes_once_then_relatches():
    c = SupportModeController()
    c.enter_soft()
    m = ToolRestrictionMiddleware(controller=c)

    c.grant_unlock("disconnect_sc_sidecar_binding", "operator authorized")
    assert await m.on_call_tool(
        _ctx("disconnect_sc_sidecar_binding"), AsyncMock(return_value="ok")
    ) == "ok"

    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(
            _ctx("disconnect_sc_sidecar_binding"), AsyncMock()
        )


async def test_unlock_is_spent_even_when_the_write_fails():
    """Otherwise a failed call leaves a second write authorized."""
    c = SupportModeController()
    c.enter_soft()
    m = ToolRestrictionMiddleware(controller=c)
    c.grant_unlock("update_rule", "operator authorized")

    failing = AsyncMock(side_effect=RuntimeError("ALTR API said no"))
    with pytest.raises(RuntimeError):
        await m.on_call_tool(_ctx("update_rule"), failing)

    assert c.pending_unlock is None
    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(_ctx("update_rule"), AsyncMock())


async def test_restricted_tools_outranks_an_unlock():
    """The operator's deny-list cannot be widened from inside a session."""
    c = SupportModeController()
    c.enter_soft()
    m = ToolRestrictionMiddleware(
        restricted_tools="update_rule", controller=c
    )
    c.grant_unlock("update_rule", "operator authorized")

    with pytest.raises(ToolError, match="access restrictions"):
        await m.on_call_tool(_ctx("update_rule"), AsyncMock())


async def test_static_allow_list_cannot_be_widened_by_the_controller():
    """SUPPORT_MODE=true plus a soft controller stays at the narrower set."""
    c = SupportModeController()
    c.enter_soft()  # soft would expose the control tools
    m = ToolRestrictionMiddleware(
        allowed_tools=SUPPORT_ALLOWED_TOOLS, controller=c
    )
    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(_ctx("exit_support_mode"), AsyncMock())


async def test_two_concurrent_calls_spend_one_unlock_exactly_once():
    """One authorization must mean one write, even under concurrency.

    The low-level MCP server dispatches each request with
    tg.start_soon(), so two calls to the same unlocked tool can be in
    flight together. The check-and-consume in on_call_tool is safe only
    because no await separates them. This test pins that: insert an await
    between the check and the consume and two writes pass on one unlock.
    """
    import asyncio

    c = SupportModeController()
    c.enter_soft()
    m = ToolRestrictionMiddleware(controller=c)
    c.grant_unlock("delete_rule", "operator authorized one removal")

    async def call():
        try:
            return await m.on_call_tool(
                _ctx("delete_rule"), AsyncMock(return_value="ok")
            )
        except ToolError:
            return "blocked"

    results = await asyncio.gather(call(), call())

    assert sorted(results) == ["blocked", "ok"], (
        f"expected exactly one write to pass, got {results}"
    )
    assert c.pending_unlock is None
    writes = [e for e in c.journal if e["action"] == "write_executed"]
    assert len(writes) == 1


async def test_listing_does_not_spend_a_pending_unlock():
    """tools/list must be a pure read of the state."""
    c = SupportModeController()
    c.enter_soft()
    m = ToolRestrictionMiddleware(controller=c)
    c.grant_unlock("update_rule", "operator authorized")

    listed = await m.on_list_tools(
        MagicMock(),
        AsyncMock(return_value=[_tool("get_tags"), _tool("update_rule")]),
    )
    assert {t.name for t in listed} == {"get_tags", "update_rule"}
    assert c.pending_unlock == "update_rule"


async def test_list_hides_writes_once_armed():
    c = SupportModeController()
    m = ToolRestrictionMiddleware(controller=c)
    tools = [_tool("get_tags"), _tool("disconnect_database")]

    before = await m.on_list_tools(MagicMock(), AsyncMock(return_value=tools))
    assert len(before) == 2

    c.enter_soft()
    after = await m.on_list_tools(MagicMock(), AsyncMock(return_value=tools))
    assert [t.name for t in after] == ["get_tags"]
