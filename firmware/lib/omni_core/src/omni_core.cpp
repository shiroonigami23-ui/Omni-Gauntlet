#include "omni_core.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace omni {

// =================================================================== SHA-256
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

static inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

static void compress(uint32_t h[8], const uint8_t block[64]) {
  uint32_t w[64];
  for (int i = 0; i < 16; i++)
    w[i] = (uint32_t)block[4 * i] << 24 | (uint32_t)block[4 * i + 1] << 16 |
           (uint32_t)block[4 * i + 2] << 8 | (uint32_t)block[4 * i + 3];
  for (int i = 16; i < 64; i++) {
    uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
    uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }
  uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
  for (int i = 0; i < 64; i++) {
    uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
    uint32_t ch = (e & f) ^ (~e & g);
    uint32_t t1 = hh + S1 + ch + K[i] + w[i];
    uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
    uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
    uint32_t t2 = S0 + maj;
    hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
  }
  h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

void Sha256::init() {
  static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  memcpy(h, iv, sizeof iv);
  len = 0;
  fill = 0;
}

void Sha256::update(const uint8_t* data, size_t n) {
  len += n;
  while (n > 0) {
    size_t take = 64 - fill < n ? 64 - fill : n;
    memcpy(buf + fill, data, take);
    fill += take; data += take; n -= take;
    if (fill == 64) { compress(h, buf); fill = 0; }
  }
}

void Sha256::final(uint8_t out[32]) {
  uint64_t bits = len * 8;
  uint8_t pad = 0x80;
  update(&pad, 1);
  uint8_t zero = 0;
  while (fill != 56) update(&zero, 1);
  uint8_t lenBytes[8];
  for (int i = 0; i < 8; i++) lenBytes[i] = (uint8_t)(bits >> (56 - 8 * i));
  update(lenBytes, 8);
  for (int i = 0; i < 8; i++) {
    out[4 * i] = h[i] >> 24; out[4 * i + 1] = h[i] >> 16;
    out[4 * i + 2] = h[i] >> 8; out[4 * i + 3] = h[i];
  }
}

void hmacSha256(const uint8_t* key, size_t keyLen, const uint8_t* msg, size_t msgLen, uint8_t out[32]) {
  uint8_t k[64] = {0};
  if (keyLen > 64) {
    Sha256 s; s.init(); s.update(key, keyLen); s.final(k);
  } else {
    memcpy(k, key, keyLen);
  }
  uint8_t ipad[64], opad[64];
  for (int i = 0; i < 64; i++) { ipad[i] = k[i] ^ 0x36; opad[i] = k[i] ^ 0x5c; }
  uint8_t inner[32];
  Sha256 s;
  s.init(); s.update(ipad, 64); s.update(msg, msgLen); s.final(inner);
  s.init(); s.update(opad, 64); s.update(inner, 32); s.final(out);
}

void macHex(const uint8_t* key, size_t keyLen, const char* body, size_t bodyLen, char out[33]) {
  static const char hx[] = "0123456789abcdef";
  uint8_t mac[32];
  hmacSha256(key, keyLen, (const uint8_t*)body, bodyLen, mac);
  for (int i = 0; i < 16; i++) { out[2 * i] = hx[mac[i] >> 4]; out[2 * i + 1] = hx[mac[i] & 15]; }
  out[32] = 0;
}

static int hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

size_t parseHexKey(const char* hex, uint8_t* out, size_t maxLen) {
  size_t n = strlen(hex);
  if (n % 2 || n / 2 > maxLen || n < 32) return 0;
  for (size_t i = 0; i < n / 2; i++) {
    int a = hexVal(hex[2 * i]), b = hexVal(hex[2 * i + 1]);
    if (a < 0 || b < 0) return 0;
    out[i] = (uint8_t)(a << 4 | b);
  }
  return n / 2;
}

size_t verifyDatagram(const uint8_t* key, size_t keyLen, char* data, size_t len, const char** body) {
  if (len < 34) return 0;
  size_t bar = len - 33;
  if (data[bar] != '|') return 0;
  char expect[33];
  macHex(key, keyLen, data, bar, expect);
  uint8_t diff = 0;
  for (int i = 0; i < 32; i++) diff |= (uint8_t)(expect[i] ^ data[bar + 1 + i]);
  if (diff) return 0;
  data[bar] = 0;
  *body = data;
  return bar;
}

// =================================================================== filters
static const float RAD2DEG = 57.2957795f;

float accelPitch(float ax, float ay, float az) { return atan2f(-ax, sqrtf(ay * ay + az * az)) * RAD2DEG; }
float accelRoll(float ay, float az) { return atan2f(ay, az) * RAD2DEG; }

void Attitude::update(float ax, float ay, float az, float gxDps, float gyDps, float dt, float alpha) {
  float ap = accelPitch(ax, ay, az), ar = accelRoll(ay, az);
  if (!primed) { pitch = ap; roll = ar; primed = true; return; }
  pitch = alpha * (pitch + gyDps * dt) + (1 - alpha) * ap;
  roll = alpha * (roll + gxDps * dt) + (1 - alpha) * ar;
}

float Flex::normalise(int raw) const {
  float span = bent - straight;
  if (fabsf(span) < 1) return 0;
  float v = (raw - straight) / span;
  return v < 0 ? 0 : (v > 1 ? 1 : v);
}

bool Flex::update(float norm, float on, float off) {
  if (!clicked && norm >= on) clicked = true;
  else if (clicked && norm <= off) clicked = false;
  return clicked;
}

// =================================================================== haptics
static const uint16_t P_TICK[] = {40, 0};
static const uint16_t P_DOUBLE[] = {50, 80, 50, 0};
static const uint16_t P_MODE0[] = {120, 0};
static const uint16_t P_MODE1[] = {80, 80, 80, 0};
static const uint16_t P_MODE2[] = {80, 80, 80, 80, 80, 0};
static const uint16_t P_ALERT[] = {300, 100, 300, 0};
static const uint16_t P_BOOT[] = {200, 0};
static const uint16_t P_CAL[] = {60, 60, 60, 60, 200, 0};

const uint16_t* hapticPattern(const char* name) {
  if (!strcmp(name, "tick")) return P_TICK;
  if (!strcmp(name, "double")) return P_DOUBLE;
  if (!strcmp(name, "mode0")) return P_MODE0;
  if (!strcmp(name, "mode1")) return P_MODE1;
  if (!strcmp(name, "mode2")) return P_MODE2;
  if (!strcmp(name, "alert")) return P_ALERT;
  if (!strcmp(name, "boot")) return P_BOOT;
  if (!strcmp(name, "calibrated")) return P_CAL;
  return nullptr;
}

void HapticPlayer::start(const uint16_t* p, uint32_t now) {
  pattern = p; step = 0; stepStart = now;
}

bool HapticPlayer::motorOn(uint32_t now) {
  if (!pattern) return false;
  while (pattern[step] && now - stepStart >= pattern[step]) {
    stepStart += pattern[step];
    step++;
  }
  if (!pattern[step]) { pattern = nullptr; return false; }
  return (step % 2) == 0;  // even steps = on, odd = off
}

// =================================================================== messages
size_t buildFrameBody(const Frame& f, char* out, size_t cap) {
  int n = snprintf(out, cap,
                   "{\"v\":1,\"type\":\"imu\",\"id\":\"%s\",\"b\":%lu,\"s\":%lu,\"t\":%lu,"
                   "\"p\":%.2f,\"r\":%.2f,\"gx\":%.1f,\"gz\":%.1f,\"a\":%.3f,\"f\":%.3f,\"c\":%d}",
                   f.device, (unsigned long)f.boot, (unsigned long)f.seq, (unsigned long)f.tMs,
                   f.pitch, f.roll, f.gx, f.gz, f.amag, f.flex, f.click ? 1 : 0);
  return (n > 0 && (size_t)n < cap) ? (size_t)n : 0;
}

size_t signInPlace(const uint8_t* key, size_t keyLen, char* buf, size_t n, size_t cap) {
  if (n + 34 > cap) return 0;
  char mac[33];
  macHex(key, keyLen, buf, n, mac);
  buf[n] = '|';
  memcpy(buf + n + 1, mac, 33);
  return n + 33;
}

static const char* findField(const char* body, const char* field) {
  char pat[24];
  snprintf(pat, sizeof pat, "\"%s\":", field);
  const char* p = strstr(body, pat);
  return p ? p + strlen(pat) : nullptr;
}

bool jsonString(const char* body, const char* field, char* out, size_t cap) {
  const char* p = findField(body, field);
  if (!p || *p != '"') return false;
  p++;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < cap) out[i++] = *p++;
  out[i] = 0;
  return *p == '"';
}

bool jsonInt(const char* body, const char* field, long* out) {
  const char* p = findField(body, field);
  if (!p) return false;
  char* end;
  long v = strtol(p, &end, 10);
  if (end == p) return false;
  *out = v;
  return true;
}

int batteryPercent(float volts) {
  int pct = (int)lroundf((volts - 3.3f) / (4.2f - 3.3f) * 100.0f);
  return pct < 0 ? 0 : (pct > 100 ? 100 : pct);
}

}  // namespace omni
