"""Unit tests for support read-only mode.

The first tests check the allow-list in altr_mcp/modes.py against the
live registry. The rest cover ToolRestrictionMiddleware's allow-list.
"""
import asyncio
import os

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from unittest.mock import AsyncMock, MagicMock

from altr_mcp.middleware import ToolRestrictionMiddleware
from altr_mcp.modes import (
    DISCLOSURE_TOOLS,
    SEARCH_POST_TOOLS,
    SUPPORT_ALLOWED_TOOLS,
)
from altr_mcp.support_control import CONTROL_TOOLS
from altr_mcp.tools import register_all


@pytest.fixture(scope="module")
def registry():
    """Map every registered tool name to its annotation flags."""
    os.environ.setdefault("ORG_ID", "test")
    os.environ.setdefault("MAPI_KEY", "test")
    os.environ.setdefault("MAPI_SECRET", "test")
    mcp = FastMCP("test")
    register_all(mcp)
    loop = asyncio.new_event_loop()
    try:
        tools = loop.run_until_complete(mcp.list_tools())
    finally:
        loop.close()
    return {
        t.name: {
            "read_only": bool(
                t.annotations and t.annotations.readOnlyHint
            ),
            "destructive": bool(
                t.annotations and t.annotations.destructiveHint
            ),
        }
        for t in tools
    }


# ── The allow-list versus the live registry ─────────────────────────────

def test_every_allowed_tool_is_registered(registry):
    """No stale names: a renamed tool would stay listed and allow nothing.

    The pre-0.4.0 delete_* examples rotted this way.
    """
    stale = SUPPORT_ALLOWED_TOOLS - set(registry)
    assert not stale, f"listed in modes.py but not registered: {stale}"


def test_allowed_tools_are_read_only_or_justified_searches(registry):
    """Ties the allow-list back to the annotation system.

    A new mutating tool gets no annotation, so it fails here if listed.
    """
    unjustified = {
        name for name in SUPPORT_ALLOWED_TOOLS
        if not registry[name]["read_only"]
        and name not in SEARCH_POST_TOOLS
    }
    assert not unjustified, (
        "allowed but neither readOnlyHint nor a justified search POST:"
        f" {unjustified}"
    )


def test_every_read_only_tool_is_allowed_or_a_disclosure(registry):
    """Makes a new read-only tool a decision, not a silent omission.

    The allow-list fails closed at runtime, so a lookup added without
    touching modes.py is hidden in support mode and nothing says so.
    """
    unclassified = {
        name for name, flags in registry.items()
        if flags["read_only"]
        and name not in SUPPORT_ALLOWED_TOOLS
        and name not in DISCLOSURE_TOOLS
    }
    assert not unclassified, (
        "readOnlyHint but neither in SUPPORT_ALLOWED_TOOLS nor"
        f" DISCLOSURE_TOOLS: {sorted(unclassified)}"
    )


def test_no_destructive_tool_is_allowed(registry):
    destructive = {
        name for name in SUPPORT_ALLOWED_TOOLS
        if registry[name]["destructive"]
    }
    assert not destructive, f"destructive but allowed: {destructive}"


def test_detokenization_is_excluded_despite_read_only_hint(registry):
    """The load-bearing exclusion.

    Detokenization is readOnlyHint=True but returns real customer values.
    If an "everything readOnlyHint" allow-list fails this, the list is wrong.
    """
    for name in DISCLOSURE_TOOLS:
        assert registry[name]["read_only"] is True, (
            f"{name} is no longer annotated readOnlyHint; re-check why"
            " modes.py treats it as a special case"
        )
        assert name not in SUPPORT_ALLOWED_TOOLS, (
            f"{name} returns real customer values and must not be"
            " available in support mode"
        )


def test_justified_searches_are_actually_unannotated_and_allowed(registry):
    """The other divergence, asserted in both directions."""
    for name in SEARCH_POST_TOOLS:
        assert name in SUPPORT_ALLOWED_TOOLS, (
            f"{name} is the entry point for audit investigation and must"
            " be available in support mode"
        )
        assert registry[name]["read_only"] is False, (
            f"{name} now carries readOnlyHint; it no longer needs to be"
            " a documented exception in modes.py"
        )


def test_allow_list_size_matches_the_documented_count(registry):
    """Pin 77 and 94, which docs, .env.example and instructions_*.md
    quote, so a change to modes.py fails here and not silently."""
    assert len(SUPPORT_ALLOWED_TOOLS) == 77, (
        "if this changed on purpose, update README.md,"
        " docs/support-mode.md (which states 77 and the 78 stdio total),"
        " docs/index.md, .env.example, instructions_support.md,"
        " and instructions_mode_control.md"
    )
    withheld = set(registry) - SUPPORT_ALLOWED_TOOLS - CONTROL_TOOLS
    assert len(withheld) == 94, (
        "if this changed on purpose, update README.md, CHANGELOG.md"
        " and docs/support-mode.md"
    )


def test_allow_list_is_a_strict_subset_of_the_registry(registry):
    """Support mode must withhold something, or it is not a mode."""
    assert SUPPORT_ALLOWED_TOOLS < set(registry)


# ── Middleware allow-list behaviour ─────────────────────────────────────

def _tool(name):
    t = MagicMock()
    t.name = name
    return t


async def test_no_allow_list_leaves_everything_visible():
    """Assert the visibility the name promises, not the stored attribute.

    That reaches middleware.py's early return for "no filters at all".
    """
    m = ToolRestrictionMiddleware(None, None)
    assert m.allowed_tools is None

    tools = [_tool("get_tags"), _tool("disconnect_database")]
    listed = await m.on_list_tools(
        MagicMock(), AsyncMock(return_value=tools)
    )
    assert [t.name for t in listed] == ["get_tags", "disconnect_database"]

    context = MagicMock()
    context.message.name = "disconnect_database"
    assert await m.on_call_tool(
        context, AsyncMock(return_value="ok")
    ) == "ok"


async def test_allow_list_filters_tools_list():
    m = ToolRestrictionMiddleware(None, {"get_tags"})
    call_next = AsyncMock(
        return_value=[_tool("get_tags"), _tool("disconnect_tag")]
    )
    result = await m.on_list_tools(MagicMock(), call_next)
    assert [t.name for t in result] == ["get_tags"]


async def test_allow_list_blocks_call_with_support_mode_reason():
    m = ToolRestrictionMiddleware(None, {"get_tags"})
    context = MagicMock()
    context.message.name = "disconnect_tag"
    call_next = AsyncMock()

    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(context, call_next)
    call_next.assert_not_called()


async def test_allow_list_permits_listed_call():
    m = ToolRestrictionMiddleware(None, {"get_tags"})
    context = MagicMock()
    context.message.name = "get_tags"
    call_next = AsyncMock(return_value="result")

    assert await m.on_call_tool(context, call_next) == "result"


async def test_allow_list_fails_closed_for_unknown_tools():
    """A tool added in a future release is withheld, not exposed."""
    m = ToolRestrictionMiddleware(None, SUPPORT_ALLOWED_TOOLS)
    context = MagicMock()
    context.message.name = "get_something_added_next_release"
    call_next = AsyncMock()

    with pytest.raises(ToolError, match="support read-only mode"):
        await m.on_call_tool(context, call_next)
    call_next.assert_not_called()


async def test_deny_list_still_applies_inside_support_mode():
    """RESTRICTED_TOOLS composes with the allow-list; both are enforced."""
    m = ToolRestrictionMiddleware("get_tags", {"get_tags", "get_policies"})
    context = MagicMock()
    context.message.name = "get_tags"
    call_next = AsyncMock()

    with pytest.raises(ToolError, match="access restrictions"):
        await m.on_call_tool(context, call_next)

    listed = await m.on_list_tools(
        MagicMock(),
        AsyncMock(return_value=[_tool("get_tags"), _tool("get_policies")]),
    )
    assert [t.name for t in listed] == ["get_policies"]
