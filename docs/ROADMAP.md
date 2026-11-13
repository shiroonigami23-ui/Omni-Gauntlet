# 🗺 Roadmap — Omni-Gauntlet

> Back to the [README](../README.md).

## Where the project stands

Status: **v0.2 alpha**.

## Milestones

### Phase 1 — Prototype (Dec 2025, done)

- [x] Original design: ESP32 + MPU-6050 + flex + OLED, UDP JSON, pyautogui receiver (docs/original-design-dec-2025.pdf)

### Phase 2 — Solid software (v0.2, done)

- [x] HMAC-signed frames, replay guard, signed discovery beacons
- [x] Complementary filter, calibration, flex hysteresis, two-way haptics
- [x] Cursor dead zone + expo curve + smoothing; right click; Hacker Mode implemented
- [x] Simulator, unit + end-to-end tests, firmware-core host tests, CI with PlatformIO build
- [x] Safer hardware: TP4056, LDO, switch, transistor motor driver

### Phase 3 — First glove build

*Goal:* Real hardware, real numbers.

- [ ] Assemble the v0.2 BOM on a glove; tune thresholds on real data
- [ ] Measure end-to-end latency (glove timestamp → action) and battery life
- [ ] Record a demo video and replace concept renders with real photos

### Phase 4 — More fingers, more gestures

- [ ] Flex sensors on index + middle + thumb (scroll, drag, middle click)
- [ ] Gesture recorder + small ML classifier (custom gestures, on-device TinyML later)
- [ ] Per-app profiles (e.g. VLC, PowerPoint, games)

### Phase 5 — Product-grade

- [ ] ESP-NOW to a USB dongle that appears as a standard HID mouse (no receiver software, works on any PC)
- [ ] BLE HID mode for phones and tablets
- [ ] Custom PCB + 3D-printed wrist pod; deep sleep when idle

## 🔭 Long-term Vision

A cheap, open, hackable alternative to commercial gesture controllers: one glove that drives presentations, media, games and accessibility workflows on any computer — and a platform for experimenting with gesture recognition.

## How to help

Pick any unchecked item, open an issue to discuss the approach, then send a PR. Items in the earliest unfinished milestone are the highest priority.


---
*Last updated: 2026-11-14*
