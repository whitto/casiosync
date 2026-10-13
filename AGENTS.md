# CasioSync project instructions

CasioSync is an ESP32 Bluetooth watch companion derived from Time Transmitter V4.16. Keep the transmitter repository separate and unchanged. This project contains no LF encoders, carrier GPIO/timers, station/transmission schedules or LF APIs.

- Retain the seven-page left sidebar and responsive dark/light visual style. Ask before fundamental layout changes beyond explicitly requested feature additions.
- Preserve the validated GW-BX5600 handshake. Expand models/features only using documented working examples/captures, checked lengths, selective packet merges and clear model limits. A BLE acknowledgement is delivery evidence, not physical display verification.
- Keep all settings durable through checked atomic saves. Keep runtime history bounded in RAM, optional first-success status at most once per Brisbane day, crash dumps default Off and no continuous flash logs.
- Complete a fresh embedded reliability review and focused fault checks before publication. Review memory/stack, allocation failure, callback/task lifetime, time/deadline/rollover, network/controller recovery, config validation and flash-write frequency. Never use periodic reboots as maintenance.
- Follow the user's release order: publish the reviewed source/version and release notes before the full suite; if it finds a failure, fix it and publish a numbered revision before repeating the full suite. Preserve immutable tags and report actual results.
- User requested compiled packages for Node32s and ESP32-C3 SuperMini. Build each target with Arduino-ESP32 3.3.12, retain the exact ELF/debug symbols and hashes, verify flash offsets/chip/partition fit and package flashing instructions. Distinguish board compilation from physical watch/board testing.
- Keep version/revision, IDE-visible newest-first changelog, UI labels, scripts, binary manifests, README and release notes consistent. Original credits and third-party licenses must remain.
- Provide direct source ZIP and compiled-package GitHub download links after publication; verify those downloads.

Reuse /workspace/.radioclock-tools and its pinned packages; do not create a Git worktree unless requested. Run python3 scripts/embed-ui.py after HTML edits. Build using bash scripts/compile.sh (CASIOSYNC_BOARD=node32s or esp32c3), then the applicable image/ELF checks. Run bash scripts/test.sh only after publishing. Local build output is outside the checkout; compiled release packages are explicit user-requested artifacts.
