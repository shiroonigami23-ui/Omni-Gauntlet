# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).
The project's docs/ROADMAP.md lists what comes next.

## [0.2.1] - 2026-11-14

### Fixed
- **Discovery:** the receiver broadcast beacons to UDP 4211 while the glove listened on 4212, so the glove could never find the host. Beacons now go to the glove port (4212).
- **Pitch sign:** "fingers up" produced negative pitch, so the upright mode gesture could not trigger. The axis convention is now documented and unit-tested, with `*_SIGN` overrides in `config.h`.
- **Roll wrap-around:** turning the palm past ±180° no longer averages the two ends into a bogus ~0°.
- **Clicks:** left click fired on the first frame of a bend, followed by a stray right click on hold. Left click now fires on release, the cursor freezes while the finger is bent, and a long hold gives a right click only.
- **Fail-safe:** glove moves are clamped one pixel inside the screen edges, and a real fail-safe pauses control for 3 s instead of crashing the receiver.

### Added
- Flex ADC smoothing (EMA) against ESP32 ADC noise.
- Optional fixed `HOST_IP` for networks that block broadcast.
- OLED redraws only when its text changes; I2C at 400 kHz, so the 66 Hz sensor loop never stalls.

## [0.2.0] - 2026-11-14

### Added
- ESP32 firmware (PlatformIO): complementary filter, boot calibration (gyro bias, neutral pose, flex range), flex hysteresis, signed UDP frames, broadcast discovery, two-way haptics, OLED status, BOOT-button recalibration.
- `omni_core`: host-testable SHA-256/HMAC, attitude filter, flex, haptic patterns and framing.
- Python receiver `omni-receiver`: signed protocol with a replay guard, cursor mapper, gesture engine (Mouse, Media, Presentation and shake "Hacker Mode"), simulator, and `keygen` / `run` / `simulate` commands.
- Hardware guide: updated BOM (charger, LDO, switch, transistor motor driver), wiring diagram, power budget.
- CI: Python tests (3.11–3.13), firmware-core host tests, PlatformIO ESP32 build artifact.

## [0.1.0] - 2025-12-17

### Added
- Original design: ESP32 + MPU-6050 + flex sensor + OLED, UDP JSON, pyautogui receiver (`docs/original-design-dec-2025.pdf`).
