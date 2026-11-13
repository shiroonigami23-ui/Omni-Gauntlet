"""Wire protocol shared by the glove firmware, the receiver and the simulator.

Every datagram is ``<json-body>|<mac>`` where ``mac`` is the first 32 hex characters
(128 bits) of HMAC-SHA256(key, json-body). The MAC covers the exact bytes that were
sent, so no canonical JSON form is needed on either side.

Message types (``type`` field):

* ``imu``     glove -> receiver, ~66 Hz sensor frame
* ``beacon``  receiver -> broadcast, lets the glove discover the host automatically
* ``haptic``  receiver -> glove, asks the glove to buzz a named pattern
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

PROTOCOL_VERSION = 1
MAC_HEX_LEN = 32
DATA_PORT = 4210      # glove -> receiver (imu frames)
BEACON_PORT = 4211    # receiver -> broadcast (discovery)
GLOVE_PORT = 4212     # glove listens here (beacons are addressed to it, haptics come back here)
MAX_DATAGRAM = 512


class ProtocolError(ValueError):
    """Raised for malformed, unauthenticated or unsupported datagrams."""


def generate_key() -> str:
    """Return a new random 128-bit pairing key as 32 hex characters."""
    return secrets.token_hex(16)


def parse_key(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        return key
    key = key.strip()
    try:
        raw = bytes.fromhex(key)
    except ValueError as exc:
        raise ValueError("pairing key must be hex (run `omni-receiver keygen`)") from exc
    if len(raw) < 16:
        raise ValueError("pairing key must be at least 16 bytes (32 hex characters)")
    return raw


def sign(body: bytes, key: bytes) -> str:
    return hmac.new(key, body, hashlib.sha256).hexdigest()[:MAC_HEX_LEN]


def encode(message: dict, key: bytes) -> bytes:
    body = json.dumps(message, separators=(",", ":")).encode()
    return body + b"|" + sign(body, key).encode()


def decode(datagram: bytes, key: bytes) -> dict:
    if len(datagram) > MAX_DATAGRAM:
        raise ProtocolError("datagram too large")
    body, sep, mac = datagram.rpartition(b"|")
    if not sep or len(mac) != MAC_HEX_LEN:
        raise ProtocolError("missing or malformed MAC")
    if not hmac.compare_digest(sign(body, key).encode(), mac):
        raise ProtocolError("bad MAC (wrong pairing key or tampered packet)")
    try:
        message = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("body is not valid JSON") from exc
    if not isinstance(message, dict) or message.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    return message


@dataclass(frozen=True)
class ImuFrame:
    """One sensor frame from the glove (angles relative to the calibrated neutral pose)."""

    device: str
    boot: int        # random id chosen at every boot (replay protection across reboots)
    seq: int         # increments every frame
    t_ms: int        # glove uptime in ms
    pitch: float     # deg, + = fingers up
    roll: float      # deg, + = tilt right
    gx: float        # deg/s, roll rate  (wrist "doorknob" twist)
    gz: float        # deg/s, yaw rate   (sideways swipe)
    amag: float      # |acceleration| in g (1.0 at rest)
    flex: float      # 0.0 = finger straight, 1.0 = fully bent (calibrated)
    click: bool      # flex past threshold, with hysteresis applied on the glove

    @classmethod
    def from_message(cls, m: dict) -> "ImuFrame":
        if m.get("type") != "imu":
            raise ProtocolError("not an imu frame")
        try:
            return cls(
                device=str(m["id"]), boot=int(m["b"]), seq=int(m["s"]), t_ms=int(m["t"]),
                pitch=float(m["p"]), roll=float(m["r"]), gx=float(m["gx"]), gz=float(m["gz"]),
                amag=float(m["a"]), flex=float(m["f"]), click=bool(m["c"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolError(f"incomplete imu frame: {exc}") from exc

    def to_message(self) -> dict:
        return {
            "v": PROTOCOL_VERSION, "type": "imu", "id": self.device, "b": self.boot, "s": self.seq,
            "t": self.t_ms, "p": round(self.pitch, 2), "r": round(self.roll, 2),
            "gx": round(self.gx, 1), "gz": round(self.gz, 1), "a": round(self.amag, 3),
            "f": round(self.flex, 3), "c": int(self.click),
        }


class ReplayGuard:
    """Rejects replayed or out-of-order frames.

    Per device we remember the current boot id and the highest sequence number seen.
    A new boot id is accepted once (the glove rebooted); frames from a boot id we have
    already moved past are rejected, so recorded traffic cannot be replayed later.
    """

    def __init__(self) -> None:
        self._current: dict[str, tuple[int, int]] = {}
        self._retired: dict[str, set[int]] = {}

    def accept(self, frame: ImuFrame) -> bool:
        retired = self._retired.setdefault(frame.device, set())
        if frame.boot in retired:
            return False
        state = self._current.get(frame.device)
        if state is None or state[0] != frame.boot:
            if state is not None:
                retired.add(state[0])
            self._current[frame.device] = (frame.boot, frame.seq)
            return True
        if frame.seq <= state[1]:
            return False
        self._current[frame.device] = (frame.boot, frame.seq)
        return True


def beacon_message(port: int, name: str) -> dict:
    return {"v": PROTOCOL_VERSION, "type": "beacon", "port": port, "name": name[:32]}


def haptic_message(pattern: str, seq: int) -> dict:
    return {"v": PROTOCOL_VERSION, "type": "haptic", "pattern": pattern, "s": seq}
