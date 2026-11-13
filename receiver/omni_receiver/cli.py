"""Command line: run the receiver, simulate a glove, or create a pairing key."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from . import __version__
from . import config as C
from . import protocol as P
from .actions import DryRunBackend, PyAutoGuiBackend
from .server import Receiver
from .simulator import SimulatedGlove


def _load(args) -> C.ReceiverConfig:
    cfg = C.load(args.config)
    if getattr(args, "key", None):
        cfg.key = args.key
    if not cfg.key:
        sys.exit(f"No pairing key. Run `omni-receiver keygen`, or set {C.KEY_ENV}.")
    return cfg


def cmd_keygen(args) -> None:
    key = P.generate_key()
    path = Path(args.config) if args.config else C.DEFAULT_PATH
    if path.exists() and not args.force:
        sys.exit(f"{path} already exists (use --force to overwrite).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(C.EXAMPLE.format(key=key))
    print(f"Wrote {path}")
    print("\nPut the same key in firmware/include/secrets.h:")
    print(f'  #define OMNI_KEY "{key}"')


def cmd_run(args) -> None:
    cfg = _load(args)
    if args.port:
        cfg.data_port = args.port
    backend = DryRunBackend(echo=True) if args.dry_run else PyAutoGuiBackend()
    rx = Receiver(cfg, backend, verbose=True)
    print(f"omni-receiver {__version__} listening on udp/{rx.port}, "
          f"beacons to udp/{cfg.glove_port} ({'dry run' if args.dry_run else 'LIVE control'})")
    print("Mode: MOUSE. Hold your hand upright + flex to switch modes. Ctrl+C to quit.")
    try:
        stats = rx.serve()
    except KeyboardInterrupt:
        rx.stop()
        stats = rx.stats
    print(f"\nframes={stats.frames} bad_mac={stats.rejected_mac} "
          f"replayed={stats.rejected_replay} malformed={stats.malformed}")


def cmd_simulate(args) -> None:
    cfg = _load(args) if not args.demo_key else C.ReceiverConfig(key=P.generate_key())
    if args.target:
        host, _, port = args.target.partition(":")
        glove = SimulatedGlove(cfg.key_bytes)
        n = glove.run(host, int(port or P.DATA_PORT))
        print(f"sent {n} frames to {args.target}")
        return
    # Self-contained demo: start a dry-run receiver on a free port and drive it.
    cfg.data_port = 0
    backend = DryRunBackend(echo=True)
    rx = Receiver(cfg, backend, verbose=True)
    t = threading.Thread(target=rx.serve, kwargs={"beacon": False}, daemon=True)
    t.start()
    SimulatedGlove(cfg.key_bytes).run("127.0.0.1", rx.port, realtime=not args.fast)
    time.sleep(0.4)
    rx.stop()
    t.join(1)
    s = rx.stats
    print(f"\nframes={s.frames} actions={len(backend.names())} final mode={rx.engine.mode_name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="omni-receiver", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("-c", "--config", help=f"config file (default {C.DEFAULT_PATH})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen", help="create a config file with a new pairing key")
    k.add_argument("--force", action="store_true")
    k.set_defaults(func=cmd_keygen)

    r = sub.add_parser("run", help="listen for the glove and control this computer")
    r.add_argument("--key")
    r.add_argument("--port", type=int)
    r.add_argument("--dry-run", action="store_true", help="print actions instead of performing them")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("simulate", help="run the scripted gesture tour without hardware")
    s.add_argument("--key")
    s.add_argument("--demo-key", action="store_true", help="use a throwaway key (no config needed)")
    s.add_argument("--target", help="send to a running receiver at host:port instead of a built-in dry run")
    s.add_argument("--fast", action="store_true", help="don't sleep between frames")
    s.set_defaults(func=cmd_simulate)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
