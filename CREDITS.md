# Credits and source provenance

CasioSync V0.1 is derived from whitto/time-transmitter V4.16 R1, source commit `2eb4e98d0857f7c33834a41761cb9f764c49cffc`. Wi-Fi/web/configuration infrastructure, time trust and Casio Bluetooth work carry forward into this separate watch-only project. LF encoders and transmitter functionality were removed.

Original ancestry notices are retained in the Arduino sketch:

- taroh / tarohs — nisejjy, copyright 2021.
- 5Breeze — ClockWaveXmitter improvements, copyright 2025.
- whitto — Time Transmitter / RadioClock and CasioSync project development.

Protocol references and independently implemented packet helpers use public examples/captures from izivkov/gshock_api, pinned commit `ae817310dd9551d5e6e53ee61d89af4e8d954767`, and izivkov/gshock-smart-sync-webapp, pinned commit `5b3ff83dbae43a7a526232e5f35de98425ca7ac8`. Exact references and differences are documented in WATCH_SUPPORT.md and WATCH_FEATURES.md. The catalog incorporates MIT-licensed model metadata: its full copyright/permission notice is preserved in `licenses/gshock_api-MIT.txt` (Ivo Zivkov, 2023).

Third-party libraries/platforms:

- Arduino-ESP32 and ESP-IDF — Espressif and contributors.
- NimBLE-Arduino / Apache Mynewt NimBLE — h2zero, Apache and contributors; original LICENSE/NOTICE files remain with the vendored source and its patch provenance.
- ArduinoJson — Benoît Blanchon and contributors.
- RadioBoundedWebServer — source-pinned derivative of Arduino-ESP32 WebServer by Ivan Grokhotkov, Hristo Gochkov and Espressif contributors. Original LGPL notices/license, source hashes and patch are retained.
- RadioCrashDumpGate — Time Transmitter source-only linker/wrapper helper; CasioSync 1.0.1 adds the ESP32-C3 metadata marker while preserving the gate implementation.

The project does not claim Casio affiliation or physical validation of every advertised model. Watch-command mappings and captures are credited to their sources; source/transport checks are described separately from hardware acceptance.
