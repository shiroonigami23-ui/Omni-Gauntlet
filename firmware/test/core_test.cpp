// Host unit tests for omni_core (no Arduino needed). Build & run: make -C test
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../lib/omni_core/src/omni_core.h"

using namespace omni;

static int failures = 0, checks = 0;
#define CHECK(cond)                                                       \
  do {                                                                    \
    checks++;                                                             \
    if (!(cond)) { failures++; printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); } \
  } while (0)

static void hex(const uint8_t* b, size_t n, char* out) {
  for (size_t i = 0; i < n; i++) sprintf(out + 2 * i, "%02x", b[i]);
}

static void test_sha256() {
  uint8_t d[32]; char h[65];
  Sha256 s; s.init(); s.update((const uint8_t*)"abc", 3); s.final(d); hex(d, 32, h);
  CHECK(!strcmp(h, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
  s.init(); s.final(d); hex(d, 32, h);
  CHECK(!strcmp(h, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
  uint8_t a[1000]; memset(a, 'a', sizeof a);
  s.init(); s.update(a, 1000); s.final(d); hex(d, 32, h);  // crosses many block boundaries
  CHECK(!strcmp(h, "41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3"));
}

static void test_hmac() {
  // RFC 4231 test case 2
  uint8_t d[32]; char h[65];
  const char* msg = "what do ya want for nothing?";
  hmacSha256((const uint8_t*)"Jefe", 4, (const uint8_t*)msg, strlen(msg), d); hex(d, 32, h);
  CHECK(!strcmp(h, "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"));
  // Same vector as receiver/tests (Python hmac): proves glove and host agree.
  uint8_t key[16];
  CHECK(parseHexKey("00112233445566778899aabbccddeeff", key, sizeof key) == 16);
  const char* body = "{\"v\":1,\"type\":\"beacon\",\"port\":4210,\"name\":\"omni-host\"}";
  char mac[33];
  macHex(key, 16, body, strlen(body), mac);
  CHECK(!strcmp(mac, "b1459fc11edb8d1ccaf316c444590d32"));
  CHECK(parseHexKey("abcd", key, sizeof key) == 0);
  CHECK(parseHexKey("zz112233445566778899aabbccddeeff", key, sizeof key) == 0);
}

static void test_sign_verify() {
  uint8_t key[16];
  parseHexKey("00112233445566778899aabbccddeeff", key, 16);
  Frame f{"gauntlet-01", 123456, 7, 105, 12.345f, -3.5f, 1.25f, -200.0f, 1.002f, 0.75f, true};
  char buf[256];
  size_t n = buildFrameBody(f, buf, sizeof buf);
  CHECK(n > 0);
  CHECK(strstr(buf, "\"p\":12.35") || strstr(buf, "\"p\":12.34"));
  CHECK(strstr(buf, "\"c\":1"));
  size_t m = signInPlace(key, 16, buf, n, sizeof buf);
  CHECK(m == n + 33 && buf[n] == '|');
  printf("sample datagram: %s\n", buf);

  char copy[256]; memcpy(copy, buf, m + 1);
  const char* body = nullptr;
  CHECK(verifyDatagram(key, 16, copy, m, &body) == n);
  long s = 0; CHECK(jsonInt(body, "s", &s) && s == 7);
  char id[32]; CHECK(jsonString(body, "id", id, sizeof id) && !strcmp(id, "gauntlet-01"));

  memcpy(copy, buf, m + 1);
  copy[10] ^= 1;  // tamper
  CHECK(verifyDatagram(key, 16, copy, m, &body) == 0);
  uint8_t other[16] = {0};
  memcpy(copy, buf, m + 1);
  CHECK(verifyDatagram(other, 16, copy, m, &body) == 0);
  CHECK(signInPlace(key, 16, buf, n, n + 10) == 0);  // no room
}

static void test_attitude() {
  Attitude a;
  a.update(0, 0, 1, 0, 0, 0.015f, 0.98f);           // flat
  CHECK(fabsf(a.pitch) < 0.01f && fabsf(a.roll) < 0.01f);
  for (int i = 0; i < 400; i++) a.update(-0.5f, 0, 0.866f, 0, 0, 0.015f, 0.98f);  // tilted 30 deg
  CHECK(fabsf(a.pitch - 30.0f) < 0.5f);
  Attitude b; b.update(0, 0, 1, 0, 0, 0.015f, 0.98f);
  for (int i = 0; i < 10; i++) b.update(0, 0, 1, 0, 100.0f, 0.015f, 0.98f);  // pure gyro motion
  CHECK(b.pitch > 5.0f && b.pitch < 15.0f);         // integrates, mildly pulled back by accel
}

static void test_flex() {
  Flex f; f.straight = 1000; f.bent = 3000;
  CHECK(f.normalise(1000) == 0.0f && f.normalise(3000) == 1.0f);
  CHECK(fabsf(f.normalise(2000) - 0.5f) < 1e-6f);
  CHECK(f.normalise(-5) == 0.0f && f.normalise(5000) == 1.0f);
  CHECK(!f.update(0.5f, 0.6f, 0.4f));
  CHECK(f.update(0.65f, 0.6f, 0.4f));
  CHECK(f.update(0.5f, 0.6f, 0.4f));               // hysteresis keeps it held
  CHECK(!f.update(0.35f, 0.6f, 0.4f));
  Flex inv; inv.straight = 3000; inv.bent = 1000;  // wiring that reads the other way round
  CHECK(fabsf(inv.normalise(1000) - 1.0f) < 1e-6f);
}

static void test_haptics() {
  CHECK(hapticPattern("tick") && hapticPattern("mode2") && !hapticPattern("nope"));
  HapticPlayer p;
  p.start(hapticPattern("double"), 1000);           // 50 on, 80 off, 50 on
  CHECK(p.motorOn(1000)); CHECK(p.motorOn(1049));
  CHECK(!p.motorOn(1050)); CHECK(!p.motorOn(1129));
  CHECK(p.motorOn(1130)); CHECK(!p.motorOn(1180));
  CHECK(!p.motorOn(5000));
}

static void test_misc() {
  long port = 0;
  CHECK(jsonInt("{\"v\":1,\"type\":\"beacon\",\"port\":4210}", "port", &port) && port == 4210);
  char t[16];
  CHECK(jsonString("{\"type\":\"haptic\",\"pattern\":\"mode1\"}", "pattern", t, sizeof t) && !strcmp(t, "mode1"));
  CHECK(!jsonString("{\"a\":1}", "pattern", t, sizeof t));
  CHECK(batteryPercent(4.2f) == 100 && batteryPercent(3.3f) == 0 && batteryPercent(3.75f) == 50);
  CHECK(batteryPercent(5.0f) == 100 && batteryPercent(2.0f) == 0);
}

int main() {
  test_sha256(); test_hmac(); test_sign_verify(); test_attitude(); test_flex(); test_haptics(); test_misc();
  printf("%d/%d checks passed\n", checks - failures, checks);
  return failures ? 1 : 0;
}
