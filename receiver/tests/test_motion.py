from omni_receiver.motion import CursorConfig, CursorMapper


def run(m, pitch, roll, n=60):
    tx = ty = 0
    for _ in range(n):
        dx, dy = m.step(pitch, roll)
        tx += dx
        ty += dy
    return tx, ty


def test_deadzone_holds_still():
    assert run(CursorMapper(), 4.0, -5.0) == (0, 0)


def test_directions():
    tx, ty = run(CursorMapper(), 0, 20)
    assert tx > 0 and ty == 0
    tx, ty = run(CursorMapper(), 20, 0)
    assert ty < 0 and tx == 0, "fingers up moves the cursor up"
    tx, ty = run(CursorMapper(CursorConfig(invert_y=True)), 20, 0)
    assert ty > 0


def test_expo_curve_bigger_tilt_is_much_faster():
    small = run(CursorMapper(), 0, 12)[0]
    big = run(CursorMapper(), 0, 30)[0]
    assert big > 3 * small > 0


def test_max_step_caps_speed():
    m = CursorMapper(CursorConfig(max_step=10, smoothing=1.0))
    assert m.step(0, 89) == (10, 0)


def test_slow_motion_accumulates_subpixels():
    m = CursorMapper(CursorConfig(smoothing=1.0))
    tx, _ = run(m, 0, 6.6, n=100)  # ~0.4 px/frame
    assert tx > 5


def test_smoothing_stops_cleanly():
    m = CursorMapper()
    run(m, 0, 30)
    run(m, 0, 0, n=40)
    assert m.step(0, 0) == (0, 0)
