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


def test_glove_discovers_host_and_receives_haptics():
    """Acts exactly like the firmware: listen on the glove port, learn the host from
    the signed beacon, send frames from that same socket, get haptics back on it."""
    import socket as S
    from omni_receiver.simulator import Pose

    key = P.generate_key()
    glove_sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
    glove_sock.bind(("127.0.0.1", 0))
    glove_sock.settimeout(3)
    cfg = ReceiverConfig(key=key, bind="127.0.0.1", data_port=0,
                         beacon_address="127.0.0.1", glove_port=glove_sock.getsockname()[1],
                         beacon_interval_s=0.1)
    rx = Receiver(cfg, DryRunBackend())
    t = threading.Thread(target=rx.serve, daemon=True)
    t.start()

    data, (host_ip, _) = glove_sock.recvfrom(512)          # 1. beacon arrives on the glove port
    beacon = P.decode(data, cfg.key_bytes)
    assert beacon["type"] == "beacon" and beacon["port"] == rx.port

    glove = SimulatedGlove(cfg.key_bytes)                     # 2. frames to the advertised port
    for pose in [Pose()] * 3 + [Pose(flex=0.9)] * 3 + [Pose()] * 3:
        glove_sock.sendto(glove.frame(pose), (host_ip, beacon["port"]))
        time.sleep(0.015)

    haptic = None                                             # 3. click -> haptic back to the glove
    deadline = time.time() + 3
    while time.time() < deadline:
        msg = P.decode(glove_sock.recvfrom(512)[0], cfg.key_bytes)
        if msg["type"] == "haptic":
            haptic = msg
            break
    rx.stop()
    t.join(2)
    glove_sock.close()
    assert haptic is not None and haptic["pattern"] == "tick"
