"""A software glove: produces the same signed frames as the firmware.

Used for development without hardware, for the end-to-end tests, and for demos.
"""

from __future__ import annotations

import random
import socket
import time
from dataclasses import dataclass
from typing import Iterator

from . import protocol as P

FRAME_DT = 0.015  # ~66 Hz, same as the firmware


@dataclass
class Pose:
    pitch: float = 0.0
    roll: float = 0.0
    gx: float = 0.0
    gz: float = 0.0
    amag: float = 1.0
    flex: float = 0.0

    @property
    def click(self) -> bool:
        return self.flex > 0.6


def _hold(pose: Pose, seconds: float) -> Iterator[Pose]:
    for _ in range(max(1, int(seconds / FRAME_DT))):
        yield pose


def _ramp(a: Pose, b: Pose, seconds: float) -> Iterator[Pose]:
    n = max(1, int(seconds / FRAME_DT))
    for i in range(1, n + 1):
        t = i / n
        yield Pose(*(x + (y - x) * t for x, y in zip(
            (a.pitch, a.roll, a.gx, a.gz, a.amag, a.flex),
            (b.pitch, b.roll, b.gx, b.gz, b.amag, b.flex))))


def tour() -> Iterator[tuple[str, Pose]]:
    """Scripted walkthrough of every gesture: (label, pose) per frame."""
    rest = Pose()
    for p in _hold(rest, 0.3):
        yield "rest", p
    for p in _ramp(rest, Pose(roll=25), 0.3):
        yield "tilt right (cursor moves right)", p
    for p in _hold(Pose(roll=25), 0.5):
        yield "tilt right (cursor moves right)", p
    for p in _ramp(Pose(roll=25), Pose(pitch=-20), 0.3):
        yield "tilt down (cursor moves down)", p
    for p in _hold(rest, 0.3):
        yield "rest", p
    for p in _hold(Pose(flex=0.9), 0.1):
        yield "quick flex (left click on release)", p
    for p in _hold(rest, 0.3):
        yield "rest", p
    for p in _hold(Pose(flex=0.9), 1.0):
        yield "hold flex 1 s (right click)", p
    for p in _hold(rest, 0.4):
        yield "rest", p
    label = "upright + flex (mode -> MEDIA)"
    for p in _hold(Pose(pitch=75), 0.2):
        yield label, p
    for p in _hold(Pose(pitch=75, flex=0.9), 0.15):
        yield label, p
    for p in _hold(rest, 0.4):
        yield "rest", p
    for p in _hold(Pose(gx=200), 0.3):
        yield "twist right (volume up)", p
    for p in _hold(Pose(gx=-200), 0.15):
        yield "twist left (volume down)", p
    for p in _hold(rest, 0.3):
        yield "rest", p
    for p in _hold(Pose(flex=0.9), 0.1):
        yield "flex (play/pause)", p
    for p in _hold(rest, 1.1):
        yield "rest", p
    for p in _hold(Pose(pitch=75), 0.2):
        yield "upright + flex (mode -> PRESENTATION)", p
    for p in _hold(Pose(pitch=75, flex=0.9), 0.15):
        yield "upright + flex (mode -> PRESENTATION)", p
    for p in _hold(rest, 0.4):
        yield "rest", p
    for p in _hold(Pose(gz=260), 0.08):
        yield "swipe right (next slide)", p
    for p in _hold(rest, 0.6):
        yield "rest", p
    for p in _hold(Pose(gz=-260), 0.08):
        yield "swipe left (previous slide)", p
    for p in _hold(rest, 0.6):
        yield "rest", p
    for p in _hold(Pose(amag=3.4), 0.05):
        yield "violent shake (hacker mode: show desktop)", p
    for p in _hold(rest, 0.3):
        yield "rest", p


class SimulatedGlove:
    def __init__(self, key: bytes, device: str = "sim-glove", noise: float = 0.3, seed: int = 7) -> None:
        self.key = key
        self.device = device
        self.boot = random.Random(seed).getrandbits(31)
        self.seq = 0
        self.t0 = time.monotonic()
        self.noise = noise
        self._rng = random.Random(seed)

    def frame(self, pose: Pose) -> bytes:
        self.seq += 1
        n = self._rng.gauss
        f = P.ImuFrame(
            device=self.device, boot=self.boot, seq=self.seq,
            t_ms=int((time.monotonic() - self.t0) * 1000),
            pitch=pose.pitch + n(0, self.noise), roll=pose.roll + n(0, self.noise),
            gx=pose.gx + n(0, self.noise * 5), gz=pose.gz + n(0, self.noise * 5),
            amag=max(0.0, pose.amag + n(0, 0.01)), flex=min(1.0, max(0.0, pose.flex)),
            click=pose.click,
        )
        return P.encode(f.to_message(), self.key)

    def run(self, host: str, port: int, realtime: bool = True, verbose: bool = True) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        last = None
        sent = 0
        for label, pose in tour():
            if verbose and label != last and label != "rest":
                print(f"[glove] {label}")
            last = label
            sock.sendto(self.frame(pose), (host, port))
            sent += 1
            # Real time mimics the glove; "fast" still paces lightly so UDP buffers don't overflow.
            time.sleep(FRAME_DT if realtime else 0.001)
        sock.close()
        return sent

