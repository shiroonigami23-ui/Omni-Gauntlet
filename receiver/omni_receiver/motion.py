"""Tilt-to-cursor mapping: dead zone, exponential response curve and smoothing."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class CursorConfig:
    deadzone_deg: float = 6.0     # ignore small tilts (natural hand tremor)
    gain: float = 0.25            # pixels per frame at 1 degree past the dead zone
    expo: float = 1.6             # >1: fine control near centre, fast at large tilts
    max_step: float = 45.0        # pixels per frame cap
    smoothing: float = 0.35       # EMA factor in (0, 1]; lower = smoother, laggier
    invert_y: bool = False


class CursorMapper:
    """Turns relative pitch/roll angles into integer mouse deltas.

    Sub-pixel remainders are carried over between frames so slow movements still
    accumulate instead of being rounded away.
    """

    def __init__(self, cfg: CursorConfig | None = None) -> None:
        self.cfg = cfg or CursorConfig()
        self._vx = 0.0
        self._vy = 0.0
        self._rx = 0.0
        self._ry = 0.0

    def _speed(self, angle: float) -> float:
        excess = abs(angle) - self.cfg.deadzone_deg
        if excess <= 0:
            return 0.0
        v = self.cfg.gain * excess ** self.cfg.expo
        return math.copysign(min(v, self.cfg.max_step), angle)

    def reset(self) -> None:
        self._vx = self._vy = self._rx = self._ry = 0.0

    def step(self, pitch: float, roll: float) -> tuple[int, int]:
        a = self.cfg.smoothing
        target_x = self._speed(roll)
        target_y = self._speed(pitch) * (1 if self.cfg.invert_y else -1)
        self._vx += a * (target_x - self._vx)
        self._vy += a * (target_y - self._vy)
        if target_x == 0 and abs(self._vx) < 0.05:
            self._vx = 0.0
        if target_y == 0 and abs(self._vy) < 0.05:
            self._vy = 0.0
        self._rx += self._vx
        self._ry += self._vy
        dx, dy = int(self._rx), int(self._ry)
        self._rx -= dx
        self._ry -= dy
        return dx, dy
