"""Unit tests for the server entrypoint (altr_mcp/server.py).

Exercises the missing-env error path, the transport branch in main(), and
the version reported to clients, without actually starting an MCP server.
"""
import asyncio

import fastmcp
import pytest

import altr_mcp
from altr_mcp.settings import get_settings
from altr_mcp.support_control import get_controller


@pytest.fixture(autouse=True)
def _clear_cache():
    """Both singletons, or the second main() in a run reuses the first.

    get_controller() decides hard versus soft on its first call, so a
    controller cached under one SUPPORT_MODE value would silently answer
    for a test that set the other.
    """
    get_settings.cache_clear()
    get_controller.cache_clear()
    yield
    get_settings.cache_clear()
    get_controller.cache_clear()


@pytest.fixture
def _restore_instructions():
    """main() mutates the module-level mcp; put it back afterwards."""
    from altr_mcp import server

    original = server.mcp.instructions
    yield
    server.mcp.instructions = original


def test_main_exits_on_missing_env(monkeypatch, capsys):
    """main() exits 1 with a helpful message if ORG_ID/MAPI_* are unset."""
    monkeypatch.delenv("ORG_ID", raising=False)
    monkeypatch.delenv("MAPI_KEY", raising=False)
    monkeypatch.delenv("MAPI_SECRET", raising=False)
    # Force dotenv not to repopulate from a .env file
    monkeypatch.setattr(
        "dotenv.load_dotenv", lambda *a, **k: False
    )

    from altr_mcp import server

    with pytest.raises(SystemExit) as exc:
        server.main([])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Missing required environment variables" in captured.err
    assert "ORG_ID" in captured.err
    assert "MAPI_KEY" in captured.err
    assert "MAPI_SECRET" in captured.err


def test_main_stdio_transport_default(monkeypatch):
    """main() with valid env starts the server on stdio by default."""
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    from altr_mcp import server

    captured_kwargs = {}

    def _fake_run(**kwargs):
        captured_kwargs.update(kwargs)

    monkeypatch.setattr(server.mcp, "run", _fake_run)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    server.main([])

    assert captured_kwargs == {"transport": "stdio"}


def test_main_http_transport_passes_host_and_port(monkeypatch):
    """main() with streamable-http transport passes host/port to run()."""
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "9000")

    from altr_mcp import server

    captured_kwargs = {}
    monkeypatch.setattr(
        server.mcp, "run",
        lambda **kw: captured_kwargs.update(kw),
    )
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    server.main([])

    assert captured_kwargs == {
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 9000,
        # Without this, uvicorn installs its own non-propagating loggers
        # after _configure_logging and bypasses the scrubbing handler.
        "uvicorn_config": {"log_config": None},
    }


@pytest.fixture
def _isolated_mcp(monkeypatch):
    """Give main() a throwaway server, so its mutations do not leak.

    main() mutates the module-level mcp in two ways that nothing undoes:
    it registers prompts, and FastMCP has no public way to unregister one;
    and it appends a ToolRestrictionMiddleware, which accumulates. A test
    that runs main() with SUPPORT_MODE or RESTRICTED_TOOLS set therefore
    leaves an allow-list filter attached to the real server for every test
    after it. Prefer this fixture for any test that calls main().
    """
    from fastmcp import FastMCP

    from altr_mcp import server

    # Built with the base instructions, like the real module-level server.
    # main() only reassigns instructions when it has something to append,
    # so a bare FastMCP would leave them None and misrepresent production.
    monkeypatch.setattr(
        server, "mcp", FastMCP("test", instructions=server._INSTRUCTIONS)
    )
    return server


def _run_main_capturing_middleware(monkeypatch):
    """Run main() without starting a server, returning middleware kwargs."""
    from altr_mcp import server

    captured = {}
    real = server.ToolRestrictionMiddleware

    def _capture(**kwargs):
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(server, "ToolRestrictionMiddleware", _capture)
    monkeypatch.setattr(server.mcp, "run", lambda **kw: None)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    # Explicit argv: main() parses sys.argv[1:] when given none, which
    # under pytest is pytest's own flags.
    server.main([])
    return captured, server


def test_support_mode_off_by_default(monkeypatch, _isolated_mcp):
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.delenv("SUPPORT_MODE", raising=False)

    captured, server = _run_main_capturing_middleware(monkeypatch)

    assert captured["allowed_tools"] is None
    assert "SUPPORT READ-ONLY MODE IS ACTIVE" not in server.mcp.instructions
    # No hint either, by default. The block steers the model to latch the
    # server read-only, so a user who never opted in should not get it and
    # then need walking through the exit phrase to undo it.
    assert "SUPPORT READ-ONLY MODE IS AVAILABLE" not in (
        server.mcp.instructions
    )
    assert captured["controller"].state == "off"


def test_hint_ships_only_when_prompts_are_published(
        monkeypatch, _isolated_mcp):
    """The hint is gated with the prompts, and on stdio only."""
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_PROMPTS", "true")
    monkeypatch.delenv("SUPPORT_MODE", raising=False)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    _, server = _run_main_capturing_middleware(monkeypatch)

    assert "SUPPORT READ-ONLY MODE IS AVAILABLE" in server.mcp.instructions


@pytest.mark.parametrize("support_mode", [None, "true"])
@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
def test_no_hint_or_prompts_on_http_transports(
        monkeypatch, _isolated_mcp, transport, support_mode):
    """Arming refuses on HTTP in every state, hard mode included.

    Parametrised over SUPPORT_MODE because the unset case alone missed a
    real bug: the prompts gate read `stdio or support_mode`, so hard mode
    published all eight on HTTP where their first step cannot succeed.
    """
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_PROMPTS", "true")
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    if support_mode is None:
        monkeypatch.delenv("SUPPORT_MODE", raising=False)
    else:
        monkeypatch.setenv("SUPPORT_MODE", support_mode)

    _, server = _run_main_capturing_middleware(monkeypatch)

    assert "SUPPORT READ-ONLY MODE IS AVAILABLE" not in (
        server.mcp.instructions
    )
    assert _prompt_names(_isolated_mcp) == set()


async def test_hard_mode_exposes_arming_and_withholds_standdown(
        monkeypatch, _isolated_mcp):
    """Assert through the protocol, not through the middleware kwargs.

    This is the test that was missing. main() passes both a static
    allow-list and the controller, and _effective_allow_list() intersects
    them, so a static list omitting MODE_ENTRY_TOOLS silently stripped
    arming in hard mode. Asserting on captured kwargs cannot catch that,
    because the kwargs were exactly what the buggy line set. Every
    published prompt opens by calling enter_support_mode, so this is the
    one configuration where that has to work.
    """
    from fastmcp import Client

    from altr_mcp.modes import SUPPORT_ALLOWED_TOOLS

    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_MODE", "true")
    # This test calls the tool, and arming succeeds on stdio only, so an
    # exported MCP_TRANSPORT in the shell or CI job would fail it.
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    from altr_mcp.tools import register_all
    register_all(_isolated_mcp.mcp)
    _run_main_capturing_middleware(monkeypatch)

    async with Client(_isolated_mcp.mcp) as client:
        names = {t.name for t in await client.list_tools()}
        # Listed is not enough. The prompt's first step is a call, and a
        # tool that lists but blocks on tools/call is a distinct failure.
        result = await client.call_tool("enter_support_mode", {})

    assert result.data["success"] is True
    assert result.data["data"]["state"] == "hard"
    assert result.data["data"]["changed"] is False
    assert len(names) == len(SUPPORT_ALLOWED_TOOLS) + 1
    assert "enter_support_mode" in names
    assert "exit_support_mode" not in names
    assert "request_write_unlock" not in names
    # Hard mode still withholds writes; arming being reachable is not a hole.
    assert "disconnect_database" not in names
    assert "critical_detokenize" not in names
    assert "get_tags" in names


def test_support_mode_env_produces_a_hard_controller(
        monkeypatch, _isolated_mcp):
    """SUPPORT_MODE must be a guarantee, not a default.

    A soft controller here would mean exit_support_mode could stand down
    a mode the operator set in configuration.
    """
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_MODE", "true")

    captured, _ = _run_main_capturing_middleware(monkeypatch)

    assert captured["controller"].is_hard is True


def _prompt_names(server):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return {p.name for p in loop.run_until_complete(
            server.mcp.list_prompts()
        )}
    finally:
        loop.close()


def test_prompts_are_not_published_by_default(monkeypatch, _isolated_mcp):
    """Publishing a prompt is a customer-facing change, not a side effect.

    A registered prompt shows up in every user's prompt menu the moment
    they upgrade. Off by default means a version bump cannot ship one.
    """
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.delenv("SUPPORT_PROMPTS", raising=False)

    _run_main_capturing_middleware(monkeypatch)

    assert _prompt_names(_isolated_mcp) == set()


@pytest.mark.parametrize("support_mode", [None, "true"])
def test_support_prompts_publishes_all_eight(
        monkeypatch, _isolated_mcp, support_mode):
    """Published on stdio in both states.

    Parametrised over SUPPORT_MODE because the gate's comment says "stdio
    only, hard mode included" and only the negative half was asserted:
    narrowing it to `stdio and not support_mode` would otherwise pass.
    Hard mode is where arming matters most, since every prompt opens with
    it.
    """
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_PROMPTS", "true")
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    if support_mode is None:
        monkeypatch.delenv("SUPPORT_MODE", raising=False)
    else:
        monkeypatch.setenv("SUPPORT_MODE", support_mode)

    _run_main_capturing_middleware(monkeypatch)

    names = _prompt_names(_isolated_mcp)
    assert len(names) == 8
    assert all(n.startswith("altr_") for n in names)


def test_support_mode_restricts_tools_and_appends_instructions(
        monkeypatch, _isolated_mcp):
    """The instructions must actually reach mcp.instructions.

    They are built at import time, before load_dotenv() runs, so main()
    has to reassign them. FastMCP exposes instructions as a property that
    writes through to the low-level server reported in initialize; if a
    future version stops doing that, this test is what catches it.
    """
    from altr_mcp.modes import SUPPORT_ALLOWED_TOOLS
    from altr_mcp.support_control import MODE_ENTRY_TOOLS

    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_MODE", "true")
    # The allow-list includes arming on stdio only, so pin the transport.
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    captured, server = _run_main_capturing_middleware(monkeypatch)

    # Arming is included on purpose. The middleware intersects this static
    # list with the controller's live one, so omitting MODE_ENTRY_TOOLS
    # here strips enter_support_mode in hard mode. The protocol-level test
    # above is what actually constrains that; this only pins the kwarg.
    assert captured["allowed_tools"] == (
        SUPPORT_ALLOWED_TOOLS | MODE_ENTRY_TOOLS
    )
    assert "SUPPORT READ-ONLY MODE IS ACTIVE" in server.mcp.instructions
    # The base instructions are kept, not replaced.
    assert "ALTR MCP server for managing data security" in (
        server.mcp.instructions
    )


@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
async def test_hard_mode_on_http_does_not_offer_arming(
        monkeypatch, _isolated_mcp, transport):
    """Arming refuses on HTTP in every state, so do not advertise it.

    Offering it there is a tool whose only possible outcome is an error,
    and it keeps hard mode on HTTP at exactly the 71 lookups every doc
    advertises.
    """
    from fastmcp import Client

    from altr_mcp.modes import SUPPORT_ALLOWED_TOOLS
    from altr_mcp.support_control import CONTROL_TOOLS
    from altr_mcp.tools import register_all

    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_MODE", "true")
    monkeypatch.setenv("MCP_TRANSPORT", transport)

    register_all(_isolated_mcp.mcp)
    captured, _ = _run_main_capturing_middleware(monkeypatch)

    assert captured["allowed_tools"] == SUPPORT_ALLOWED_TOOLS

    # Through the protocol, not just the kwarg: six files advertise 71
    # here, and the kwarg cannot see what the intersection does.
    async with Client(_isolated_mcp.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert len(names) == len(SUPPORT_ALLOWED_TOOLS)
    assert not (names & CONTROL_TOOLS)


def test_support_mode_composes_with_restricted_tools(
        monkeypatch, _isolated_mcp):
    monkeypatch.setenv("ORG_ID", "org")
    monkeypatch.setenv("MAPI_KEY", "key")
    monkeypatch.setenv("MAPI_SECRET", "secret")
    monkeypatch.setenv("SUPPORT_MODE", "1")
    monkeypatch.setenv("RESTRICTED_TOOLS", "get_tags")

    captured, _ = _run_main_capturing_middleware(monkeypatch)

    assert captured["restricted_tools"] == "get_tags"
    assert captured["allowed_tools"] is not None


def test_server_info_version_is_ours_not_fastmcps():
    """The MCP handshake reports our version, not the framework's.

    FastMCP falls back to its own version when the server is constructed
    without version=, which is what clients saw before: serverInfo.version
    was fastmcp's 3.2.4 while the package was 0.5.4.
    """
    from altr_mcp import server

    async def _handshake():
        from fastmcp import Client

        async with Client(server.mcp) as client:
            return client.initialize_result.serverInfo.version

    reported = asyncio.run(_handshake())
    assert reported == altr_mcp.__version__, (
        f"clients are told {reported!r}; the package is "
        f"{altr_mcp.__version__!r} (fastmcp is {fastmcp.__version__!r})"
    )


def test_version_flag_prints_package_version(capsys):
    """--version prints the package version and exits 0."""
    from altr_mcp import server

    with pytest.raises(SystemExit) as exc:
        server.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"altr-mcp {altr_mcp.__version__}"


def test_version_flag_needs_no_credentials(monkeypatch, capsys):
    """--version works with no ORG_ID/MAPI_* set.

    Asking a program its version must not require credentials, so the flag
    is handled before any settings are loaded.
    """
    monkeypatch.delenv("ORG_ID", raising=False)
    monkeypatch.delenv("MAPI_KEY", raising=False)
    monkeypatch.delenv("MAPI_SECRET", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    from altr_mcp import server

    with pytest.raises(SystemExit) as exc:
        server.main(["--version"])
    assert exc.value.code == 0
    assert altr_mcp.__version__ in capsys.readouterr().out


def test_unknown_flag_is_rejected(capsys):
    """An unrecognized flag errors instead of silently starting the server."""
    from altr_mcp import server

    with pytest.raises(SystemExit) as exc:
        server.main(["--nope"])
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_main_registers_both_middlewares(monkeypatch, test_env):
    """main() installs both middlewares.

    The middleware tests register by hand, so only this test covers main().
    """
    from altr_mcp import server as server_mod
    from altr_mcp.middleware import (
        ToolRestrictionMiddleware, ValidationRedactionMiddleware)

    monkeypatch.setattr(server_mod.mcp, "run", lambda **kwargs: None)
    server_mod.main([])

    installed = [type(m) for m in server_mod.mcp.middleware]
    assert ValidationRedactionMiddleware in installed
    assert ToolRestrictionMiddleware in installed
    # Registered first means outermost: FastMCP wraps in reverse order.
    assert installed.index(ValidationRedactionMiddleware) < \
        installed.index(ToolRestrictionMiddleware)
