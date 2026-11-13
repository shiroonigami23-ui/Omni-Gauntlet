"""Receiver configuration: TOML file + environment overrides."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .gestures import GestureConfig
from .motion import CursorConfig
from .protocol import BEACON_PORT, DATA_PORT, parse_key

DEFAULT_PATH = Path.home() / ".config" / "omni-gauntlet" / "receiver.toml"
KEY_ENV = "OMNI_GAUNTLET_KEY"


@dataclass
class ReceiverConfig:
    key: str = ""
    bind: str = "0.0.0.0"
    data_port: int = DATA_PORT
    beacon_port: int = BEACON_PORT
    beacon_interval_s: float = 1.0
    beacon_address: str = "255.255.255.255"
    name: str = "omni-host"
    gestures: GestureConfig = field(default_factory=GestureConfig)

    @property
    def key_bytes(self) -> bytes:
        return parse_key(self.key)


def _apply(obj, data: dict) -> None:
    names = {f.name for f in fields(obj)}
    for k, v in data.items():
        if k not in names:
            raise ValueError(f"unknown config option: {k}")
        if isinstance(v, dict):
            _apply(getattr(obj, k), v)
        else:
            setattr(obj, k, v)


def load(path: str | os.PathLike | None = None) -> ReceiverConfig:
    cfg = ReceiverConfig()
    p = Path(path) if path else DEFAULT_PATH
    if p.exists():
        with open(p, "rb") as fh:
            data = tomllib.load(fh)
        cursor = data.get("gestures", {}).pop("cursor", None)
        _apply(cfg, data)
        if cursor:
            _apply(cfg.gestures.cursor, cursor)
    elif path:
        raise FileNotFoundError(p)
    if os.environ.get(KEY_ENV):
        cfg.key = os.environ[KEY_ENV]
    return cfg


EXAMPLE = """\
# Omni-Gauntlet receiver configuration
key = "{key}"            # must match OMNI_KEY in firmware/include/secrets.h
name = "my-laptop"
data_port = 4210
beacon_port = 4211

[gestures]
upright_deg = 60.0
twist_rate_dps = 120.0
swipe_rate_dps = 180.0
shake_g = 2.6

[gestures.cursor]
deadzone_deg = 6.0
gain = 0.25
expo = 1.6
smoothing = 0.35
invert_y = false
"""

__all__ = ["ReceiverConfig", "load", "EXAMPLE", "DEFAULT_PATH", "KEY_ENV", "CursorConfig"]
