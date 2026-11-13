from omni_receiver.actions import DryRunBackend, show_desktop_keys
from omni_receiver.gestures import GestureEngine
from omni_receiver.protocol import ImuFrame

DT = 0.015


class Clock:
    t = 0.0


def make(system="Linux"):
    b = DryRunBackend()
    haptics = []
    e = GestureEngine(b, haptic=haptics.append, system=system)
    return e, b, haptics


def feed(e, clock, seconds, **pose):
    base = dict(pitch=0.0, roll=0.0, gx=0.0, gz=0.0, amag=1.0, flex=0.0, click=False)
    base.update(pose)
    for _ in range(max(1, int(seconds / DT))):
        clock.t += DT
        e.process(ImuFrame(device="g", boot=1, seq=0, t_ms=0, **base), clock.t)


def test_click_and_right_click():
    e, b, h = make()
    c = Clock()
    feed(e, c, 0.2)
    feed(e, c, 0.1, click=True)
    feed(e, c, 0.3)
    feed(e, c, 1.0, click=True)
    assert b.names() == ["click left", "click left", "click right"]
    assert h == ["tick", "tick", "double"]


def test_upright_flex_cycles_modes_without_clicking():
    e, b, h = make()
    c = Clock()
    assert e.mode_name == "MOUSE"
    feed(e, c, 0.2, pitch=75)
    feed(e, c, 0.1, pitch=75, click=True)
    assert e.mode_name == "MEDIA"
    assert b.names() == []
    assert h == ["mode1"]
    feed(e, c, 0.1, pitch=75)
    feed(e, c, 0.1, pitch=75, click=True)
    assert e.mode_name == "MEDIA", "cooldown prevents double switching"
    feed(e, c, 1.0, pitch=75)
    feed(e, c, 0.1, pitch=75, click=True)
    assert e.mode_name == "PRESENTATION"


def test_media_volume_and_playpause():
    e, b, _ = make()
    e.mode = 1
    c = Clock()
    feed(e, c, 0.3, gx=200)
    feed(e, c, 0.2)
    feed(e, c, 0.1, click=True)
    names = b.names()
    assert 2 <= names.count("press volumeup") <= 3, "rate limited"
    assert names[-1] == "press playpause"


def test_presentation_swipes():
    e, b, _ = make()
    e.mode = 2
    c = Clock()
    feed(e, c, 0.1, gz=260)
    feed(e, c, 0.6)
    feed(e, c, 0.1, gz=-260)
    assert b.names() == ["press right", "press left"]


def test_shake_shows_desktop_in_any_mode():
    for mode in range(3):
        e, b, h = make(system="Windows")
        e.mode = mode
        c = Clock()
        feed(e, c, 0.05, amag=3.5)
        feed(e, c, 0.05, amag=3.5)
        assert b.names() == ["hotkey win d"], "once, thanks to the cooldown"
        assert h[-1] == "alert"


def test_show_desktop_keys_per_os():
    assert show_desktop_keys("Windows") == ("win", "d")
    assert show_desktop_keys("Linux") == ("super", "d")
    assert show_desktop_keys("Darwin") == ("command", "m")


def test_cursor_moves_only_in_mouse_mode():
    e, b, _ = make()
    c = Clock()
    feed(e, c, 0.5, roll=25)
    assert any(ev[0] == "move" for ev in b.events)
    e2, b2, _ = make()
    e2.mode = 1
    feed(e2, Clock(), 0.5, roll=25)
    assert not any(ev[0] == "move" for ev in b2.events)
