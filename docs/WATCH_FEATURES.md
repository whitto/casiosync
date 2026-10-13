# Watch features in CasioSync V0.1

CasioSync retains the GW-BX5600 time handshake and adds optional watch settings. Time synchronization remains the primary transaction. Watch settings are disabled by default, configured per watch profile, and applied only after the watch connects to CasioSync. Saving a choice does not wake or initiate a connection on the watch.

The model catalog identifies 122 Casio advertised-name candidates. Optional features are offered for the 119 standard/BX protocol candidates with source-derived capability records. The three analogue candidates are time-only in V0.1. Unknown models cannot receive optional settings writes. A supported name indicates a protocol candidate, **not hardware validation of every feature on that watch**.

## Settings available

| Feature | Desired value | Selective behavior |
| --- | --- | --- |
| Alarms | Five alarm on/off switches, hour 0–23, minute 0–59 | Enable the alarm group to apply all five. Preserve record flags and reserved bytes that are unrelated to these fields. |
| Hourly chime | Keep / off / on | Change the first alarm packet's chime bit without changing its alarm when the alarm group is disabled. |
| Countdown timer | Hours, minutes and seconds | Apply the selected countdown start duration; does not start, pause or reset a running countdown through a separate invented command. |
| Display time format | Keep / 12-hour / 24-hour | Change only the format bit. |
| Button tone | Keep / off / on | Preserve other sound/vibration flags; handle the known short and extended settings layouts. |
| Auto light | Keep / off / on | Offered when the upstream model record says that the feature exists. |
| Watch power saving | Keep / off / on | Watch setting, separate from the ESP32 Wi-Fi power schedule. |
| Light duration | Keep / short / long | The watch defines the actual seconds associated with short/long; these labels differ by model. |
| Date order | Keep / month-day / day-month | Offered where the upstream model record supports it. |
| Weekday language | Keep / English / Spanish / French / German / Italian / Russian | Offered where the upstream model record supports it. |
| Watch automatic adjustment | Keep, or enable/disable with minute after the hour 0–59 | The watch determines the actual automatic-adjustment hours. This is not the ESP32 listening schedule and cannot select arbitrary new daily hours. |
| GW-BX5600 font | Keep / Standard / Classic | Existing separate font preference; unrelated settings writes preserve the font byte. |
| Battery information | Latest value from a connected-watch condition reply | Existing read-only battery information; the UI identifies missing or unsupported battery evidence. |

The thirteen digital-square candidates GW-BX5600, GW-B5600, GW-B5600#, GW-B5000, GMW-B5000, GMW-B5000#, GMW-BZ5000, MRG-B5000, MRG-B5000#, GCW-B5000, DW-B5600, TRN-50 and PRJ-BW002 allow a duration of 1 second through 24 hours. Other candidate models are conservatively limited by CasioSync to 1 second through 1 hour while their exact timer maximum remains unconfirmed. This is a software limit, not a claim that those watches have a one-hour hardware maximum. A watch can reject a requested value; readback must confirm it before CasioSync reports the setting as confirmed.

## Packet evidence and preservation

The production helper is [CasioWatchFeatures.h](../firmware/CasioSync_V0_1/CasioWatchFeatures.h). It is independently implemented from the following pinned public references:

- [gshock_api watch model metadata](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/watch_info.py).
- [gshock_api alarm I/O](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/iolib/alarms_io.py), [timer I/O](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/iolib/timer_io.py), [settings I/O](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/iolib/settings_io.py) and [automatic adjustment I/O](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/iolib/time_adjustment_io.py).
- [Smart Sync web app I/O](https://github.com/izivkov/gshock-smart-sync-webapp/tree/5b3ff83dbae43a7a526232e5f35de98425ca7ac8/src/api/io), especially AlarmsIO, TimerIO, SettingsIO and TimeAdjustmentIO.
- [Official-app GW-BX5600 capture](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/test_data/btsnoop_hci-bx2.txt) and [BX Smart Sync capture](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/test_data/bx3_smart_sync_app.txt).

Reads use the existing all-features read-request characteristic. Writes use the existing all-features write/notify characteristic. No hard-coded attribute handles are used by the firmware.

| Header | Accepted reply shape | Fields edited |
| --- | --- | --- |
| `0x15` | Exactly 5 bytes | Alarm enable flag `0x40`, first-alarm hour/minute; optional chime flag `0x80`. |
| `0x16` | Header followed by four-byte alarm records, bounded to five alarms | Per-alarm enable `0x40`, hour/minute. Other flag bits and the second byte of every record are preserved. |
| `0x18` | Exactly 6, 7 or 15 bytes | Hours/minutes/seconds at offsets 1–3. Preserve the received length and every trailing byte. |
| `0x13` | Exactly 12 or 17 bytes | Selected basic-setting bits/fields only; extended-layout button-tone bit at offset 12 is handled explicitly. |
| `0x11` | Exactly 15 bytes | Inverse automatic-adjustment enable bit `0x80` at offset 12, minute after the hour at offset 13. Other bits and bytes remain unchanged. |

The upstream timer encoders disagree about six versus seven bytes, and an actual BX timer read contains fifteen bytes. CasioSync does not manufacture a fixed-length timer packet: it copies the valid watch reply and edits its duration. This merge is conservative, but its acceptance as a write on all candidate models still needs physical testing.

An upstream alarm encoder manufactures `0x40` for the second byte of an alarm record. A captured record also exists with that byte zero. CasioSync preserves the actual byte rather than replacing it with the encoder's assumption.

The BX time-handshake stage historically labeled “alarms” contains six `0x1f` city-name records in an SP_DATA `0x06` packet. It is **not** the five real alarm settings. That working handshake is retained unchanged. Optional real alarm settings use `0x15`/`0x16` on the separate all-features channel.

## Reliability and confirmation

The helpers use fixed-size buffers with no dynamic allocation. Invalid headers, lengths, ranges or unavailable capability bits cause failure before any output is modified. Selected fields are merged into an actual watch reply, preserving every unselected setting. Readback compares the selected fields rather than treating a GATT acknowledgement as proof that the watch adopted them.

Optional requests are admitted only while the connection has a time reserve for the final TIME write (and requested font work). The reserve is checked before submissions; it cannot guarantee that a stalled SDK ATT operation finishes promptly. Such a stall can consume the reserve and abort the whole sync at the existing 45-second transaction deadline, with normal disconnect/barrier cleanup. A setting failure or timeout is reported separately from time delivery; neither a write acknowledgement nor successful time synchronization proves that an optional setting changed. Multiple settings are separate watch transactions, so a partial update is possible if the connection closes between them.

User-selected desired settings are configuration and are retained across reboots. They remain selected for later syncs until the user turns them off or selects Keep. Runtime feature outcomes are not continuously logged to flash. The original once-per-day optional sync-status snapshot policy is retained.

[The native packet fixture](../tests/test_watch_features.cpp) checks literal BX basic, automatic-adjustment and timer read layouts; reference alarm layouts; selective merge/readback; unknown/analogue refusal; bounded ranges; in-place use; preservation of reserved bytes; and non-destructive malformed-packet failures. It runs with AddressSanitizer and UndefinedBehaviorSanitizer. These checks do not replace physical testing of newly added setting writes. The user's successful BX time-sync evidence from Time Transmitter applies to the retained time handshake, not to all optional settings in this new release.

Features without sufficient bounded protocol evidence are not exposed as working controls: hand alignment, stopwatch controls, timer start/stop, alarm snooze modes, activity/health uploads, phone notifications, reminders and world-city editing remain outside V0.1.
