#pragma once
// ---------------------------------------------------------------- pin map
#define PIN_SDA        21   // I2C: MPU-6050 + OLED
#define PIN_SCL        22
#define PIN_FLEX       34   // ADC1 (safe to use while Wi-Fi is on); 47k pull-down to GND
#define PIN_VIB        26   // vibration motor via NPN transistor + flyback diode
#define PIN_VBAT       35   // battery voltage via 100k/100k divider (optional)
#define PIN_BOOT_BTN    0   // on-board BOOT button: press to recalibrate

// ---------------------------------------------------------------- network
#define DATA_PORT      4210  // receiver listens here
#define BEACON_PORT    4211  // receiver broadcasts discovery beacons here
#define GLOVE_PORT     4212  // glove listens here (beacons + haptics)
#define BEACON_TIMEOUT_MS 5000  // forget the host if no beacon for this long

// ---------------------------------------------------------------- timing
#define FRAME_INTERVAL_MS  15   // ~66 Hz
#define OLED_INTERVAL_MS  200   // 5 Hz screen refresh
#define WIFI_TIMEOUT_MS 15000

// ---------------------------------------------------------------- sensing
#define COMP_ALPHA      0.98f  // complementary filter: gyro trust
#define FLEX_ON         0.60f  // normalised bend to start a click
#define FLEX_OFF        0.40f  // ... and to release it (hysteresis)
#define CAL_SAMPLES     200
