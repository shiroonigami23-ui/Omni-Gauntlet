// Omni-Gauntlet firmware — ESP32 + MPU-6050 + flex sensor + OLED + vibration motor.
//
// Boot:  Wi-Fi -> calibrate (hold still, then bend + straighten the index finger) -> run.
// Run:   ~66 Hz signed IMU frames to the receiver found via its broadcast beacon.
//        Haptic requests from the receiver are played without blocking the loop.
// BOOT button (GPIO0): recalibrate at any time.

#include <Adafruit_GFX.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <esp_system.h>

#include "config.h"
#include "omni_core.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#warning "include/secrets.h not found - using secrets.example.h (copy it and set your Wi-Fi + key)"
#include "secrets.example.h"
#endif

using namespace omni;

static Adafruit_MPU6050 mpu;
static Adafruit_SSD1306 oled(128, 64, &Wire, -1);
static WiFiUDP udp;

static uint8_t key[32];
static size_t keyLen = 0;
static uint32_t bootId = 0, seq = 0;

static Attitude att;
static Flex flex;
static HapticPlayer haptic;
static float gyroBias[3] = {0, 0, 0};
static float neutralPitch = 0, neutralRoll = 0;

static IPAddress host;
static uint16_t hostPort = DATA_PORT;
static char hostName[33] = "";
static uint32_t lastBeaconMs = 0;
static bool haveHost = false;

static const char* MODE_NAMES[] = {"MOUSE", "MEDIA", "SLIDES"};
static int modeIdx = 0;
static bool oledOk = false;
static float lastFlex = 0;
static bool lastClick = false;

// ------------------------------------------------------------------ helpers
static void buzz(const char* name) {
  const uint16_t* p = hapticPattern(name);
  if (p) haptic.start(p, millis());
}

static void hapticBlocking(const char* name) {
  buzz(name);
  uint32_t until = millis() + 1500;
  while (haptic.pattern && millis() < until) {
    digitalWrite(PIN_VIB, haptic.motorOn(millis()) ? HIGH : LOW);
    delay(2);
  }
  digitalWrite(PIN_VIB, LOW);
}

static void screen(const char* l1, const char* l2 = "", const char* l3 = "") {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.println(l1);
  oled.setCursor(0, 20);
  oled.println(l2);
  oled.setCursor(0, 40);
  oled.println(l3);
  oled.display();
}

static float batteryVolts() {
  // 100k/100k divider -> half the battery voltage at the pin.
  return analogReadMilliVolts(PIN_VBAT) * 2.0f / 1000.0f;
}

static void fatal(const char* what) {
  Serial.printf("FATAL: %s\n", what);
  screen("ERROR", what, "check wiring + reset");
  while (true) { hapticBlocking("alert"); delay(3000); }
}

// --------------------------------------------------------------- calibration
static void calibrate() {
  screen("CALIBRATING", "hold hand flat", "and still...");
  delay(800);
  float gs[3] = {0, 0, 0}, p = 0, r = 0, straight = 0;
  for (int i = 0; i < CAL_SAMPLES; i++) {
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    gs[0] += g.gyro.x; gs[1] += g.gyro.y; gs[2] += g.gyro.z;
    p += accelPitch(a.acceleration.x, a.acceleration.y, a.acceleration.z);
    r += accelRoll(a.acceleration.y, a.acceleration.z);
    straight += analogRead(PIN_FLEX);
    delay(5);
  }
  for (int i = 0; i < 3; i++) gyroBias[i] = gs[i] / CAL_SAMPLES;
  neutralPitch = p / CAL_SAMPLES;
  neutralRoll = r / CAL_SAMPLES;
  flex.straight = straight / CAL_SAMPLES;

  screen("CALIBRATING", "bend index finger", "fully, then relax");
  hapticBlocking("tick");
  // Track the reading furthest from "straight" over 3 s: works whichever way the divider is wired.
  float extreme = flex.straight;
  uint32_t until = millis() + 3000;
  while (millis() < until) {
    float v = analogRead(PIN_FLEX);
    if (fabsf(v - flex.straight) > fabsf(extreme - flex.straight)) extreme = v;
    delay(5);
  }
  flex.bent = extreme;
  if (fabsf(flex.bent - flex.straight) < 150) {
    // Barely any change: the sensor is probably disconnected. Keep running, clicks just won't fire.
    Serial.println("WARN: flex sensor range too small - check the 47k resistor and connections");
    flex.bent = flex.straight + 4095;
  }
  att = Attitude();
  Serial.printf("cal: gyro bias %.4f %.4f %.4f rad/s  neutral p=%.1f r=%.1f  flex %.0f..%.0f\n",
                gyroBias[0], gyroBias[1], gyroBias[2], neutralPitch, neutralRoll, flex.straight, flex.bent);
  hapticBlocking("calibrated");
}

// ------------------------------------------------------------------ network
static void connectWifi() {
  screen("OMNI-GAUNTLET", "Wi-Fi: connecting", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // lower latency; costs battery
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT_MS) fatal("Wi-Fi timeout");
    delay(100);
  }
  Serial.printf("Wi-Fi ok, ip %s\n", WiFi.localIP().toString().c_str());
  udp.begin(GLOVE_PORT);
}

static void pollIncoming(uint32_t now) {
  char buf[256];
  int size;
  while ((size = udp.parsePacket()) > 0) {
    int n = udp.read(buf, sizeof buf - 1);
    if (n <= 0) continue;
    buf[n] = 0;
    IPAddress from = udp.remoteIP();
    const char* body;
    if (!verifyDatagram(key, keyLen, buf, n, &body)) continue;  // wrong key or garbage: ignore
    char type[16];
    if (!jsonString(body, "type", type, sizeof type)) continue;
    if (!strcmp(type, "beacon")) {
      long port;
      if (jsonInt(body, "port", &port) && port > 0 && port < 65536) {
        if (!haveHost || host != from) {
          Serial.printf("host found: %s:%ld\n", from.toString().c_str(), port);
          buzz("double");
        }
        host = from;
        hostPort = (uint16_t)port;
        jsonString(body, "name", hostName, sizeof hostName);
        haveHost = true;
        lastBeaconMs = now;
      }
    } else if (!strcmp(type, "haptic")) {
      char pattern[16];
      if (jsonString(body, "pattern", pattern, sizeof pattern)) {
        buzz(pattern);
        if (!strncmp(pattern, "mode", 4)) modeIdx = (pattern[4] - '0') % 3;
      }
    }
  }
  if (haveHost && now - lastBeaconMs > BEACON_TIMEOUT_MS) {
    haveHost = false;
    Serial.println("host lost");
  }
}

static void sendFrame(const sensors_event_t& a, float gxDps, float gzDps, float flexNorm, bool click) {
  if (!haveHost) return;
  Frame f;
  f.device = DEVICE_ID;
  f.boot = bootId;
  f.seq = ++seq;
  f.tMs = millis();
  f.pitch = att.pitch - neutralPitch;
  f.roll = att.roll - neutralRoll;
  f.gx = gxDps;
  f.gz = gzDps;
  f.amag = sqrtf(a.acceleration.x * a.acceleration.x + a.acceleration.y * a.acceleration.y +
                 a.acceleration.z * a.acceleration.z) / 9.80665f;
  f.flex = flexNorm;
  f.click = click;
  char buf[320];
  size_t n = buildFrameBody(f, buf, sizeof buf);
  if (!n) return;
  n = signInPlace(key, keyLen, buf, n, sizeof buf);
  if (!n) return;
  udp.beginPacket(host, hostPort);
  udp.write((const uint8_t*)buf, n);
  udp.endPacket();
}

static void drawStatus() {
  if (!oledOk) return;
  char l1[24], l2[24], l3[24];
  snprintf(l1, sizeof l1, "%s  %ddBm", MODE_NAMES[modeIdx], (int)WiFi.RSSI());
  if (haveHost) snprintf(l2, sizeof l2, "-> %.14s", hostName[0] ? hostName : "host");
  else snprintf(l2, sizeof l2, "searching host...");
  snprintf(l3, sizeof l3, "bat %d%%  flex %d%%%s", batteryPercent(batteryVolts()),
           (int)(lastFlex * 100), lastClick ? " *" : "");
  screen(l1, l2, l3);
}

// --------------------------------------------------------------------- main
void setup() {
  Serial.begin(115200);
  pinMode(PIN_VIB, OUTPUT);
  pinMode(PIN_FLEX, INPUT);
  pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
  analogReadResolution(12);
  Wire.begin(PIN_SDA, PIN_SCL);

  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) Serial.println("WARN: OLED not found at 0x3C - continuing without display");

  keyLen = parseHexKey(OMNI_KEY, key, sizeof key);
  if (!keyLen) fatal("bad OMNI_KEY");
  if (!mpu.begin()) fatal("MPU-6050 missing");
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);  // room for the shake gesture
  mpu.setGyroRange(MPU6050_RANGE_1000_DEG);      // fast twists and swipes
  mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);

  bootId = esp_random() & 0x7fffffff;
  hapticBlocking("boot");
  connectWifi();
  calibrate();
}

void loop() {
  static uint32_t lastFrame = 0, lastOled = 0;
  uint32_t now = millis();

  digitalWrite(PIN_VIB, haptic.motorOn(now) ? HIGH : LOW);
  pollIncoming(now);

  if (digitalRead(PIN_BOOT_BTN) == LOW) {
    delay(30);
    if (digitalRead(PIN_BOOT_BTN) == LOW) calibrate();
  }
  if (WiFi.status() != WL_CONNECTED) {
    screen("Wi-Fi lost", "reconnecting...");
    WiFi.reconnect();
    delay(500);
    return;
  }

  if (now - lastFrame >= FRAME_INTERVAL_MS) {
    float dt = (now - lastFrame) / 1000.0f;
    if (dt > 0.1f) dt = FRAME_INTERVAL_MS / 1000.0f;
    lastFrame = now;
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    const float R2D = 57.2957795f;
    float gx = (g.gyro.x - gyroBias[0]) * R2D;
    float gy = (g.gyro.y - gyroBias[1]) * R2D;
    float gz = (g.gyro.z - gyroBias[2]) * R2D;
    att.update(a.acceleration.x, a.acceleration.y, a.acceleration.z, gx, gy, dt, COMP_ALPHA);
    lastFlex = flex.normalise(analogRead(PIN_FLEX));
    bool click = flex.update(lastFlex, FLEX_ON, FLEX_OFF);
    if (click && !lastClick && !haveHost) buzz("tick");  // local feedback until a host answers
    lastClick = click;
    sendFrame(a, gx, gz, lastFlex, click);
  }

  if (now - lastOled >= OLED_INTERVAL_MS) {
    lastOled = now;
    drawStatus();
  }
}
