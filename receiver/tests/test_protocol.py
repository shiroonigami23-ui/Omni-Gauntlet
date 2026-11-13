import pytest

from omni_receiver import protocol as P

KEY = bytes.fromhex("00112233445566778899aabbccddeeff")


def frame(seq=1, boot=42, **kw):
    base = dict(device="g1", boot=boot, seq=seq, t_ms=seq * 15, pitch=0.0, roll=0.0,
                gx=0.0, gz=0.0, amag=1.0, flex=0.0, click=False)
    base.update(kw)
    return P.ImuFrame(**base)


def test_roundtrip():
    f = frame(pitch=12.5, roll=-3.25, click=True)
    m = P.decode(P.encode(f.to_message(), KEY), KEY)
    assert P.ImuFrame.from_message(m) == f


def test_wrong_key_rejected():
    data = P.encode(frame().to_message(), KEY)
    with pytest.raises(P.ProtocolError, match="MAC"):
        P.decode(data, bytes(16))


def test_tampered_body_rejected():
    data = P.encode(frame().to_message(), KEY)
    tampered = data.replace(b'"c":0', b'"c":1')
    assert tampered != data
    with pytest.raises(P.ProtocolError, match="MAC"):
        P.decode(tampered, KEY)


@pytest.mark.parametrize("data", [b"", b"no-mac", b'{"v":1}|short', b"x" * 600])
def test_garbage_rejected(data):
    with pytest.raises(P.ProtocolError):
        P.decode(data, KEY)


def test_wrong_version_rejected():
    msg = frame().to_message()
    msg["v"] = 99
    with pytest.raises(P.ProtocolError, match="version"):
        P.decode(P.encode(msg, KEY), KEY)


def test_replay_guard():
    g = P.ReplayGuard()
    assert g.accept(frame(seq=1))
    assert g.accept(frame(seq=2))
    assert not g.accept(frame(seq=2)), "duplicate"
    assert not g.accept(frame(seq=1)), "old"
    assert g.accept(frame(seq=1, boot=99)), "reboot gets a fresh boot id"
    assert not g.accept(frame(seq=500, boot=42)), "recorded traffic from a past boot"


def test_key_parsing():
    assert len(P.parse_key(P.generate_key())) == 16
    with pytest.raises(ValueError):
        P.parse_key("not-hex")
    with pytest.raises(ValueError):
        P.parse_key("abcd")


def test_datagram_signed_by_firmware_core_is_accepted():
    # Printed by firmware/test/core_test.cpp (C++ SHA-256/HMAC) -> must verify in Python.
    data = (b'{"v":1,"type":"imu","id":"gauntlet-01","b":123456,"s":7,"t":105,"p":12.35,'
            b'"r":-3.50,"gx":1.2,"gz":-200.0,"a":1.002,"f":0.750,"c":1}|b94bb654c9ee6693c6fef6191dece2ab')
    f = P.ImuFrame.from_message(P.decode(data, KEY))
    assert f.device == "gauntlet-01" and f.seq == 7 and f.click and f.gz == -200.0


def test_beacon_vector_matches_firmware_core():
    body = b'{"v":1,"type":"beacon","port":4210,"name":"omni-host"}'
    assert P.sign(body, KEY) == "b1459fc11edb8d1ccaf316c444590d32"
