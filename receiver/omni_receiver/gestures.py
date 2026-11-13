"""Gesture engine: turns a stream of IMU frames into OS actions.

Modes (cycled with the mode gesture):
  0 MOUSE         tilt = cursor, flex = left click, hold flex = right click
  1 MEDIA         twist wrist (roll rate) = volume up/down, flex = play/pause
  2 PRESENTATION  quick sideways swipe (yaw rate) = next/previous slide, flex = next slide

Global gestures (any mode):
  MODE SWITCH     hand upright (pitch > upright_deg) + flex
  HACKER MODE     violent shake (|a| > shake_g) = show desktop / hide everything
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .actions import Backend, show_desktop_keys
from .motion import CursorConfig, CursorMapper
from .protocol import ImuFrame

MODES = ("MOUSE", "MEDIA", "PRESENTATION")


@dataclass
class GestureConfig:
    upright_deg: float = 60.0         # pitch above this = "hand upright"
    mode_cooldown_s: float = 1.0
    click_debounce_s: float = 0.25
    right_click_hold_s: float = 0.8
    twist_rate_dps: float = 120.0     # deg/s roll rate to count as a twist
    volume_repeat_s: float = 0.12
    swipe_rate_dps: float = 180.0     # deg/s yaw rate to count as a swipe
    swipe_cooldown_s: float = 0.5
    shake_g: float = 2.6
    shake_cooldown_s: float = 2.0
    cursor: CursorConfig = field(default_factory=CursorConfig)


class GestureEngine:
    def __init__(
        self,
        backend: Backend,
        cfg: GestureConfig | None = None,
        haptic: Callable[[str], None] | None = None,
        system: str | None = None,
    ) -> None:
        self.backend = backend
        self.cfg = cfg or GestureConfig()
        self.haptic = haptic or (lambda pattern: None)
        self.mode = 0
        self.cursor = CursorMapper(self.cfg.cursor)
        self._desktop_keys = show_desktop_keys(system)
        self._prev_click = False
        self._press_start: float | None = None
        self._right_fired = False
        self._last_click = -1e9
        self._last_mode = -1e9
        self._last_volume = -1e9
        self._last_swipe = -1e9
        self._last_shake = -1e9

    @property
    def mode_name(self) -> str:
        return MODES[self.mode]

    # ------------------------------------------------------------------ helpers
    def _rising(self, click: bool) -> bool:
        return click and not self._prev_click

    def _switch_mode(self, now: float) -> None:
        self.mode = (self.mode + 1) % len(MODES)
        self._last_mode = now
        self.cursor.reset()
        self.haptic("mode%d" % self.mode)

    # ------------------------------------------------------------------- update
    def process(self, f: ImuFrame, now: float) -> None:
        c = self.cfg
        rising = self._rising(f.click)
        upright = f.pitch > c.upright_deg

        # Global: shake -> hacker mode (show desktop). Highest priority.
        if f.amag > c.shake_g and now - self._last_shake > c.shake_cooldown_s:
            self._last_shake = now
            self.backend.hotkey(*self._desktop_keys)
            self.haptic("alert")
            self._prev_click = f.click
            return

        # Global: upright + flex -> next mode.
        if upright:
            if rising and now - self._last_mode > c.mode_cooldown_s:
                self._switch_mode(now)
            self._prev_click = f.click
            self._press_start = None
            return

        if self.mode == 0:
            self._mouse(f, now, rising)
        elif self.mode == 1:
            self._media(f, now, rising)
        else:
            self._presentation(f, now, rising)
        self._prev_click = f.click

    def _mouse(self, f: ImuFrame, now: float, rising: bool) -> None:
        c = self.cfg
        dx, dy = self.cursor.step(f.pitch, f.roll)
        self.backend.move(dx, dy)
        if rising and now - self._last_click > c.click_debounce_s:
            self._last_click = now
            self._press_start = now
            self._right_fired = False
            self.backend.click("left")
            self.haptic("tick")
        elif f.click and self._press_start is not None and not self._right_fired:
            if now - self._press_start >= c.right_click_hold_s:
                self._right_fired = True
                self.backend.click("right")
                self.haptic("double")
        if not f.click:
            self._press_start = None

    def _media(self, f: ImuFrame, now: float, rising: bool) -> None:
        c = self.cfg
        if abs(f.gx) > c.twist_rate_dps and now - self._last_volume > c.volume_repeat_s:
            self._last_volume = now
            self.backend.press("volumeup" if f.gx > 0 else "volumedown")
        if rising and now - self._last_click > c.click_debounce_s:
            self._last_click = now
            self.backend.press("playpause")
            self.haptic("tick")

    def _presentation(self, f: ImuFrame, now: float, rising: bool) -> None:
        c = self.cfg
        if abs(f.gz) > c.swipe_rate_dps and now - self._last_swipe > c.swipe_cooldown_s:
            self._last_swipe = now
            self.backend.press("right" if f.gz > 0 else "left")
            self.haptic("tick")
        if rising and now - self._last_click > c.click_debounce_s:
            self._last_click = now
            self.backend.press("right")
            self.haptic("tick")
