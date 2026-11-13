// omni_core: hardware-independent logic for the Omni-Gauntlet glove.
// Everything here compiles on a PC too, so it is unit-tested on the host
// (see firmware/test/core_test.cpp) and in CI.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace omni {

// ------------------------------------------------------------------ crypto
// Minimal SHA-256 / HMAC-SHA256 (FIPS 180-4, RFC 2104). No dynamic memory.
struct Sha256 {
  uint32_t h[8];
  uint8_t buf[64];
  uint64_t len;
  size_t fill;
  void init();
  void update(const uint8_t* data, size_t n);
  void final(uint8_t out[32]);
};

void hmacSha256(const uint8_t* key, size_t keyLen, const uint8_t* msg, size_t msgLen, uint8_t out[32]);

// First 32 hex chars (128 bits) of HMAC-SHA256 -> out (33 bytes incl. NUL).
void macHex(const uint8_t* key, size_t keyLen, const char* body, size_t bodyLen, char out[33]);

// Parse a hex key; returns number of bytes written (0 on error).
size_t parseHexKey(const char* hex, uint8_t* out, size_t maxLen);

// Verify "<body>|<mac>" in place. On success returns body length and sets *body.
// Returns 0 if malformed or the MAC does not match. Constant-time comparison.
size_t verifyDatagram(const uint8_t* key, size_t keyLen, char* data, size_t len, const char** body);

// ------------------------------------------------------------------ filters
// Complementary filter: fuses gyro (smooth, drifts) with accel (noisy, absolute).
struct Attitude {
  float pitch = 0, roll = 0;     // degrees
  bool primed = false;
  void update(float ax, float ay, float az, float gxDps, float gyDps, float dt, float alpha);
};

float accelPitch(float ax, float ay, float az);
float accelRoll(float ay, float az);

// Flex sensor: normalise between calibrated straight/bent readings, click with hysteresis.
struct Flex {
  float straight = 0, bent = 4095;
  bool clicked = false;
  float level = 0;
  bool primed = false;
  float normalise(int raw) const;
  float smooth(float norm, float alpha);         // EMA against ADC noise
  bool update(float norm, float on, float off);  // returns current click state
};

// ------------------------------------------------------------------ haptics
// Patterns are on/off durations in ms, terminated by 0. Played non-blocking.
const uint16_t* hapticPattern(const char* name);

struct HapticPlayer {
  const uint16_t* pattern = nullptr;
  uint8_t step = 0;
  uint32_t stepStart = 0;
  void start(const uint16_t* p, uint32_t now);
  bool motorOn(uint32_t now);  // call every loop; returns desired motor state
};

// ------------------------------------------------------------------ messages
struct Frame {
  const char* device;
  uint32_t boot, seq, tMs;
  float pitch, roll, gx, gz, amag, flex;
  bool click;
};

// Writes JSON body into out; returns length (0 if it does not fit).
size_t buildFrameBody(const Frame& f, char* out, size_t cap);

// Appends "|<mac>" to body in buf (body length n). Returns new length or 0.
size_t signInPlace(const uint8_t* key, size_t keyLen, char* buf, size_t n, size_t cap);

// Tiny field extractors for the receiver's small, flat JSON messages.
bool jsonString(const char* body, const char* field, char* out, size_t cap);
bool jsonInt(const char* body, const char* field, long* out);

// Battery: LiPo voltage -> rough percentage (linear between 3.3 V and 4.2 V).
int batteryPercent(float volts);

}  // namespace omni
