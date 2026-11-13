"""Simulated glove -> real UDP socket -> receiver -> dry-run backend."""

import threading
import time

from omni_receiver import protocol as P
from omni_receiver.actions import DryRunBackend
from omni_receiver.config import ReceiverConfig
from omni_receiver.server import Receiver
from omni_receiver.simulator import SimulatedGlove


def run_tour(realtime=True):
    key = P.generate_key()
    cfg = ReceiverConfig(key=key, bind="127.0.0.1", data_port=0)
    backend = DryRunBackend()
    rx = Receiver(cfg, backend)
    t = threading.Thread(target=rx.serve, kwargs={"beacon": False}, daemon=True)
    t.start()
    sent = SimulatedGlove(cfg.key_bytes).run("127.0.0.1", rx.port, realtime=realtime, verbose=False)
    time.sleep(0.5)
    rx.stop()
    t.join(2)
    return rx, backend, sent


def test_full_gesture_tour_over_udp():
    rx, backend, sent = run_tour()
    assert rx.stats.frames == sent
    names = backend.names()
    assert names[:2] == ["click left", "click right"]
    assert "press volumeup" in names and "press volumedown" in names
    assert "press playpause" in names
    i = names.index("press playpause")
    assert names[i + 1:i + 3] == ["press right", "press left"]
    assert names[-1].startswith("hotkey")
    assert rx.engine.mode_name == "PRESENTATION"
    assert any(e[0] == "move" for e in backend.events)


def test_wrong_key_glove_is_ignored():
    cfg = ReceiverConfig(key=P.generate_key(), bind="127.0.0.1", data_port=0)
    backend = DryRunBackend()
    rx = Receiver(cfg, backend)
    t = threading.Thread(target=rx.serve, kwargs={"beacon": False}, daemon=True)
    t.start()
    attacker = SimulatedGlove(bytes.fromhex(P.generate_key()))
    sent = attacker.run("127.0.0.1", rx.port, realtime=False, verbose=False)
    time.sleep(0.5)
    rx.stop()
    t.join(2)
    assert rx.stats.frames == 0
    assert 0 < rx.stats.rejected_mac <= sent  # burst send: UDP may drop some, none may pass
    assert backend.events == []


def test_replayed_capture_is_ignored():
    cfg = ReceiverConfig(key=P.generate_key(), bind="127.0.0.1", data_port=0)
    rx = Receiver(cfg, DryRunBackend())
    glove = SimulatedGlove(cfg.key_bytes)
    from omni_receiver.simulator import Pose
    captured = [glove.frame(Pose(flex=0.9)) for _ in range(5)]
    for d in captured:
        rx.handle(d, ("127.0.0.1", 9))
    for d in captured:
        rx.handle(d, ("127.0.0.1", 9))
    rx.stop()
    assert rx.stats.frames == 5
    assert rx.stats.rejected_replay == 5
