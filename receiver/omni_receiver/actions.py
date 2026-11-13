"""Output backends: the real OS (via pyautogui) or a dry-run recorder."""

from __future__ import annotations

import platform
from typing import Protocol


class Backend(Protocol):
    def move(self, dx: int, dy: int) -> None: ...
    def click(self, button: str = "left") -> None: ...
    def press(self, key: str) -> None: ...
    def hotkey(self, *keys: str) -> None: ...


def show_desktop_keys(system: str | None = None) -> tuple[str, ...]:
    """Hotkey for 'get everything off the screen' on each OS."""
    system = system or platform.system()
    if system == "Windows":
        return ("win", "d")
    if system == "Darwin":
        return ("command", "m")       # minimise the front window
    return ("super", "d")             # most Linux desktops


class DryRunBackend:
    """Records actions instead of performing them (simulation and tests)."""

    def __init__(self, echo: bool = False) -> None:
        self.events: list[tuple] = []
        self.echo = echo

    def _log(self, *event) -> None:
        self.events.append(event)
        if self.echo and event[0] != "move":
            print("  action:", " ".join(str(e) for e in event))

    def move(self, dx: int, dy: int) -> None:
        if dx or dy:
            self._log("move", dx, dy)

    def click(self, button: str = "left") -> None:
        self._log("click", button)

    def press(self, key: str) -> None:
        self._log("press", key)

    def hotkey(self, *keys: str) -> None:
        self._log("hotkey", *keys)

    def names(self) -> list[str]:
        return [" ".join(map(str, e)) for e in self.events if e[0] != "move"]


class PyAutoGuiBackend:
    """Controls the real mouse and keyboard.

    pyautogui's fail-safe stays ON: slam the real mouse into a screen corner to abort.
    """

    def __init__(self) -> None:
        try:
            import pyautogui
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise SystemExit(
                "pyautogui is not installed. Run: pip install 'omni-receiver[control]' "
                "or use --dry-run."
            ) from exc
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0
        self._g = pyautogui

    def move(self, dx: int, dy: int) -> None:
        if dx or dy:
            self._g.moveRel(dx, dy, _pause=False)

    def click(self, button: str = "left") -> None:
        self._g.click(button=button)

    def press(self, key: str) -> None:
        self._g.press(key)

    def hotkey(self, *keys: str) -> None:
        self._g.hotkey(*keys)
