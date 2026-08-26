"""Runtime support-mode state.

Support mode can be reached two ways, and they are deliberately not
equally reversible.

HARD, set by the operator via SUPPORT_MODE=true at startup. No tool can
leave it and no tool can unlock a write. Leaving it means restarting
without the flag. An operator's decision must not be undoable by the
model it was meant to constrain.

SOFT, entered at runtime by the ``enter_support_mode`` tool, which is
the first instruction in every prompt this server ships. A customer who
was never going to edit a config file still gets middleware-enforced
read-only, and it costs them nothing. Because they armed it themselves,
they are also allowed to stand it down: one named write at a time via
``request_write_unlock``, or entirely via ``exit_support_mode`` with a
typed confirmation.

The soft path is weaker than the hard path in exactly one way, and it is
worth being precise about it. Arming depends on the model making the
first call. Once armed, enforcement is identical: both run in
ToolRestrictionMiddleware, so "just delete it anyway" on a later turn
fails in the middleware rather than depending on the model's restraint.
That later turn was the failure this exists to stop.
"""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, Optional

import structlog

from altr_mcp.modes import DISCLOSURE_TOOLS, SUPPORT_ALLOWED_TOOLS

logger = structlog.get_logger(__name__)

State = Literal["off", "soft", "hard"]

#: Arming. The controller offers it in every state, including hard mode,
#: where it can only ever be a no-op reporting the mode is already on, so
#: that a published prompt whose first instruction is "call
#: enter_support_mode" is coherent under both paths; withholding it would
#: have the model open every investigation by calling a tool that does not
#: exist.
#:
#: Note that main() intersects a static allow-list over this one and omits
#: this set on the HTTP transports, where mode control refuses outright. So
#: "offered in hard mode" means offered on stdio. Do not "simplify" the two
#: lists into agreement: the static list is allowed to narrow this.
MODE_ENTRY_TOOLS = frozenset({"enter_support_mode"})

#: Standing the mode down. Soft mode only. Withheld in hard mode, because
#: a mode the operator set in configuration must not be reversible by the
#: model it was meant to constrain.
MODE_STANDDOWN_TOOLS = frozenset({
    "request_write_unlock",
    "exit_support_mode",
})

CONTROL_TOOLS = MODE_ENTRY_TOOLS | MODE_STANDDOWN_TOOLS

#: Never unlockable, at any scope, in any mode.
#:
#: Detokenization returns real customer values, and the token deletes
#: destroy them. No troubleshooting fix requires either, so "just this
#: one call" is never a good enough reason. Keeping these out means a
#: novice cannot authorize a plaintext read by agreeing to something
#: that sounded narrow.
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

    One process serves one client on stdio, so process scope is session
    scope there. That equivalence does not hold for the HTTP transports,
    which is why the control tools refuse to run on them: a soft latch
    is per-process state, and on a shared process one client's latch
    would silently restrict every other client.
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
            # Deliberately does not quote the phrase. Printing it here
            # handed the model the exact string in the same breath as
            # telling it not to supply the string, which is self-defeating.
            # The phrase is not a secret either way (it is in the docstring,
            # the docs, and the success payload), so this is a speed bump
            # rather than a gate the server can verify. See docs.
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
        # Reset, so a second arm-and-exit cycle in the same process reports
        # only its own activity. Otherwise the summary pasted into a support
        # ticket over-reports, listing writes from an earlier cycle.
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
        """Spend a pending unlock for ``tool_name``.

        Returns True if this call was covered by an unlock, which the
        middleware takes as permission to proceed. The unlock is cleared
        either way, so a refused or failed call does not leave a second
        write authorized.
        """
        if self._pending_unlock != tool_name:
            return False
        self._pending_unlock = None
        self._record("write_executed", tool=tool_name)
        logger.warning("support_mode.write_executed", tool=tool_name)
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
