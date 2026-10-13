# ESP32-C3 linker metadata marker

Arduino's precompiled-library folder selection uses the build MCU name. This directory enables the library's `ldflags` for ESP32-C3 (`esp32c3`) as the existing `src/esp32` marker does for classic ESP32. There is no precompiled archive: the C++ gate is built from source with the selected board toolchain. The same checked wrapper/default-Off behavior is retained.
