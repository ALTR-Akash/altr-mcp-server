"""Runtime support-mode state.

HARD mode (SUPPORT_MODE at startup) cannot be left or unlocked by a tool.
SOFT mode (armed by ``enter_support_mode``) can. Both enforce in
ToolRestrictionMiddleware. See docs/support-mode.md.
"""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, Optional

import structlog

from altr_mcp.modes import DISCLOSURE_TOOLS, SUPPORT_ALLOWED_TOOLS

logger = structlog.get_logger(__name__)

State = Literal["off", "soft", "hard"]

#: Offered in every state, so prompts that open with it work in hard mode,
#: where it is a no-op. main()'s static list may narrow it, as on HTTP.
MODE_ENTRY_TOOLS = frozenset({"enter_support_mode"})

#: Soft mode only: the model must not undo a mode the operator set.
MODE_STANDDOWN_TOOLS = frozenset({
    "request_write_unlock",
    "exit_support_mode",
})

CONTROL_TOOLS = MODE_ENTRY_TOOLS | MODE_STANDDOWN_TOOLS

#: Never unlockable, in any mode. These return or destroy real customer
#: values, and no troubleshooting fix needs either.
NEVER_UNLOCKABLE = DISCLOSURE_TOOLS | frozenset({
    "critical_delete_tokens",
    "vault_delete_tokens",
})

#: The phrase a human must type to leave support mode entirely.
EXIT_PHRASE = "EXIT SUPPORT MODE"


class SupportModeNotActive(Exception):
    """Raised when a mode-control call needs an active support mode."""


class SupportModeLocked(Exception):
    """Raised when a tool tries to stand down an operator-set mode."""


class UnlockRefused(Exception):
    """Raised when the requested unlock is not one we will ever grant."""


class SupportModeController:
    """Support-mode state for one server process.

    On stdio one process serves one client. On HTTP one client's latch
    would restrict every client, so the control tools refuse there.
    """

    def __init__(self, hard: bool = False) -> None:
        self._state: State = "hard" if hard else "off"
        self._pending_unlock: Optional[str] = None
        self._journal: list[dict] = []

    # ── state ───────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state in ("soft", "hard")

    @property
    def is_hard(self) -> bool:
        return self._state == "hard"

    @property
    def pending_unlock(self) -> Optional[str]:
        return self._pending_unlock

    @property
    def journal(self) -> list[dict]:
        """Everything that happened, for the exit summary."""
        return list(self._journal)

    def allowed_tools(self) -> Optional[frozenset[str]]:
        """The effective allow-list, or None when support mode is off.

        None means "no allow-list", which is not the same as the empty
        set. The middleware treats None as "everything passes".
        """
        if self._state == "off":
            return None
        allowed = SUPPORT_ALLOWED_TOOLS | MODE_ENTRY_TOOLS
        if self._state == "soft":
            allowed = allowed | MODE_STANDDOWN_TOOLS
        if self._pending_unlock is not None:
            allowed = allowed | {self._pending_unlock}
        return frozenset(allowed)

    # ── transitions ─────────────────────────────────────────────────────

    def enter_soft(self) -> bool:
        """Arm soft support mode. Returns False if already active."""
        if self.is_active:
            return False
        self._state = "soft"
        self._record("entered", detail="soft, armed by prompt")
        logger.info("support_mode.entered", mode="soft")
        return True

    def exit(self, confirmation: str) -> list[dict]:
        """Leave support mode entirely. Returns the session journal."""
        if not self.is_active:
            raise SupportModeNotActive("support mode is not active")
        if self.is_hard:
            raise SupportModeLocked(
                "support mode was set by the operator via SUPPORT_MODE"
                " and cannot be left by a tool call. Leaving it means"
                " restarting the server without SUPPORT_MODE."
            )
        if confirmation != EXIT_PHRASE:
            # Never quote the phrase in model-visible text, so the model
            # has to ask the operator for it.
            raise UnlockRefused(
                "exit_support_mode requires the operator's confirmation"
                " phrase, typed by them verbatim. Ask the operator for it;"
                " it is in the server documentation. Do not guess it or"
                " supply it yourself."
            )
        self._record("exited", detail="confirmed by typed phrase")
        summary = self.journal
        self._state = "off"
        self._pending_unlock = None
        # Reset, so the next cycle's summary lists only its own writes.
        self._journal = []
        logger.info("support_mode.exited")
        return summary

    # ── one-shot write unlock ───────────────────────────────────────────

    def grant_unlock(self, tool_name: str, reason: str) -> None:
        """Allow exactly one call to ``tool_name``, then re-latch."""
        if not self.is_active:
            raise SupportModeNotActive(
                "support mode is not active, so no unlock is needed"
            )
        if self.is_hard:
            raise SupportModeLocked(
                "support mode was set by the operator via SUPPORT_MODE."
                " Writes are not available and cannot be unlocked by a"
                " tool call."
            )
        if tool_name in NEVER_UNLOCKABLE:
            raise UnlockRefused(
                f"{tool_name} is never unlockable. It returns or"
                " destroys real customer values, and no troubleshooting"
                " step requires it."
            )
        if tool_name in SUPPORT_ALLOWED_TOOLS or tool_name in CONTROL_TOOLS:
            raise UnlockRefused(
                f"{tool_name} is already available; no unlock is needed."
            )
        if not reason or not reason.strip():
            raise UnlockRefused(
                "an unlock needs a reason describing what the operator"
                " authorized and why"
            )
        self._pending_unlock = tool_name
        self._record("unlock_granted", tool=tool_name, detail=reason.strip())
        logger.info(
            "support_mode.unlock_granted", tool=tool_name, reason=reason
        )

    def consume_unlock(self, tool_name: str) -> bool:
        """Spend a pending unlock for ``tool_name``; return whether one was.

        Runs before the call, so the journal records an attempt: a refused
        or failed call still spends the unlock.
        """
        if self._pending_unlock != tool_name:
            return False
        self._pending_unlock = None
        self._record("write_attempted", tool=tool_name)
        logger.warning("support_mode.write_attempted", tool=tool_name)
        return True

    # ── journal ─────────────────────────────────────────────────────────

    def _record(
        self,
        action: str,
        tool: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        self._journal.append({
            "action": action,
            "tool": tool,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })


@lru_cache(maxsize=1)
def get_controller() -> SupportModeController:
    """The process-wide controller.

    Cached the same way get_settings() is. Tests that need a fresh one
    call get_controller.cache_clear().
    """
    from altr_mcp.settings import get_settings

    return SupportModeController(hard=get_settings().support_mode)
