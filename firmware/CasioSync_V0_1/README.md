# CasioSync V0.1 R4 — Arduino sketch

Open `CasioSync_V0_1.ino`; keep all companion `.h` files and `partitions.csv` in this folder. The web UI is embedded, so no separate filesystem/UI upload is required.

Install Arduino-ESP32 **3.3.12**, ArduinoJson **6.21.5**, and the three included complete source libraries: NimBLE-Arduino **2.5.1-radioclock.1**, RadioBoundedWebServer **3.3.12-radioclock.1**, RadioCrashDumpGate **1.0.1**. Replace ordinary/duplicate NimBLE copies. Keep both crash-gate `src/esp32` and `src/esp32c3` metadata markers; a missing marker prevents its linker option being applied on that MCU.

Node32s: 40 MHz, No OTA (Large APP). ESP32-C3: 4MB, DIO, 40 MHz, Huge APP, USB CDC On Boot enabled. For the SuperMini discrete blue LED, define `CASIOSYNC_C3_SUPERMINI` as 1 near the top of the sketch before the LED selection block, or use `compiler.cpp.extra_flags=-DCASIOSYNC_C3_SUPERMINI=1` when compiling with Arduino CLI. Without that definition, a C3 source build uses the selected board variant's LED. The supplied compiled SuperMini package already contains the definition.

First setup: CasioSync_XXXXXX / password 12345678 / http://192.168.4.1. CasioSync settings use their own filenames/schema. Normal upgrades retain settings and do not require erase-all. An unformatted/mount-fault filesystem is preserved for explicit storage recovery in Settings.

Watch profiles, daily BT and Wi-Fi schedules, NTP trust, font/battery, fixed RAM history, daily optional success snapshot and LED behavior carry over from Time Transmitter. Optional alarms/countdown/basic preferences default Off and apply only to matching bound watches during an ESP connection. See the full repository README, model/feature docs and release notes for supported layouts and actual validation status. New protocol candidates/settings are not all physically tested.

Original ancestry credits: tarohs/nisejjy (2021), 5Breeze/ClockWaveXmitter (2025), whitto/Time Transmitter; public Casio packet/model references from izivkov/gshock_api and gshock-smart-sync-webapp. Original notices and library licenses remain.

Project: https://github.com/whitto/casiosync
