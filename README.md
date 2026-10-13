# CasioSync_V0.1_R4 — Node32s

Built for a 4 MB Node32s using Arduino-ESP32 3.3.12. Activity LED: GPIO2 active high. C3 uses native USB CDC. This package is for the stated chip; use the other package for the other board.

Install esptool 5.x (`python -m pip install esptool`) and run from this folder, replacing YOUR_PORT with the board's serial port:

```
python -m esptool --chip esp32 --port YOUR_PORT --baud 460800 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 bootloader.bin 0x8000 partitions.bin 0xe000 boot_app0.bin 0x10000 application.bin
```

For an application-only upgrade when this project's partition table is already installed:

```
python -m esptool --chip esp32 --port YOUR_PORT --baud 460800 write-flash 0x10000 application.bin
```

`factory.bin` is the merged first-install image at offset 0x0. It stops before LittleFS; it is not the CLI's padded 4 MB image. The separate-file command avoids writing the gaps containing SDK NVS. Neither command calls erase-flash. Application upgrades retain saved CasioSync settings. Boot/partition updates should use the separate images above.

After flashing, press Reset. A fresh setup uses Wi-Fi CasioSync_XXXXXX, password 12345678, browser http://192.168.4.1. A new/unformatted filesystem is retained for explicit Settings storage recovery rather than erased automatically. Existing Time Transmitter configuration has a different filename/schema; provision CasioSync separately.

If the port will not enter download mode automatically, hold BOOT while pressing/releasing RESET, then release BOOT and retry. Close Arduino Serial Monitor while uploading. Use a data-capable USB cable. The SuperMini package drives its discrete blue GPIO8 LED active-low; it is not the generic C3 RGB-LED build.

`manifest.json` records hashes, chip/flash settings, source hashes and exact validation limits. `firmware.elf.gz` contains the matching ELF for crash/backtrace decoding. These builds have not been flashed onto a physical board in this cloud environment.
