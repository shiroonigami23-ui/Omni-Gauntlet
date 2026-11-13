"""UDP receiver: discovery beacons out, authenticated IMU frames in, haptics back."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass

from . import protocol as P
from .actions import Backend
from .config import ReceiverConfig
from .gestures import GestureEngine


@dataclass
class Stats:
    frames: int = 0
    rejected_mac: int = 0
    rejected_replay: int = 0
    malformed: int = 0
    last_device: str = ""


class Receiver:
    def __init__(self, cfg: ReceiverConfig, backend: Backend, verbose: bool = False) -> None:
        self.cfg = cfg
        self.key = cfg.key_bytes
        self.stats = Stats()
        self.verbose = verbose
        self.guard = P.ReplayGuard()
        self._glove_addr: tuple[str, int] | None = None
        self._haptic_seq = 0
        self._stop = threading.Event()
        self._serving = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((cfg.bind, cfg.data_port))
        self.sock.settimeout(0.2)
        self.engine = GestureEngine(backend, cfg.gestures, haptic=self._send_haptic)

    @property
    def port(self) -> int:
        return self.sock.getsockname()[1]

    # ---------------------------------------------------------------- outbound
    def _send_haptic(self, pattern: str) -> None:
        if not self._glove_addr:
            return
        self._haptic_seq += 1
        msg = P.encode(P.haptic_message(pattern, self._haptic_seq), self.key)
        try:
            self.sock.sendto(msg, self._glove_addr)
        except OSError:
            pass
        if self.verbose:
            print(f"  haptic -> {pattern}")

    def _beacon_loop(self) -> None:
        bsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        bsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = P.encode(P.beacon_message(self.port, self.cfg.name), self.key)
        while not self._stop.is_set():
            try:
                bsock.sendto(msg, (self.cfg.beacon_address, self.cfg.glove_port))
            except OSError:
                pass
            self._stop.wait(self.cfg.beacon_interval_s)
        bsock.close()

    # ----------------------------------------------------------------- inbound
    def handle(self, data: bytes, addr: tuple[str, int], now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        try:
            frame = P.ImuFrame.from_message(P.decode(data, self.key))
        except P.ProtocolError as exc:
            if "MAC" in str(exc):
                self.stats.rejected_mac += 1
            else:
                self.stats.malformed += 1
            return
        if not self.guard.accept(frame):
            self.stats.rejected_replay += 1
            return
        self.stats.frames += 1
        self.stats.last_device = frame.device
        self._glove_addr = addr
        before = self.engine.mode
        self.engine.process(frame, now)
        if self.verbose and self.engine.mode != before:
            print(f"  mode -> {self.engine.mode_name}")

    def serve(self, duration: float | None = None, beacon: bool = True) -> Stats:
        self._serving = True
        if beacon:
            threading.Thread(target=self._beacon_loop, daemon=True).start()
        end = None if duration is None else time.monotonic() + duration
        try:
            while not self._stop.is_set() and (end is None or time.monotonic() < end):
                try:
                    data, addr = self.sock.recvfrom(P.MAX_DATAGRAM + 1)
                except socket.timeout:
                    continue
                self.handle(data, addr)
        finally:
            self._stop.set()
            self.sock.close()
        return self.stats

    def stop(self) -> None:
        """Ask serve() to finish; it closes the socket itself on the way out."""
        if self._stop.is_set():
            return
        self._stop.set()
        if not self._serving:
            self.sock.close()
