# CasioSync V0.1 watch compatibility

CasioSync carries forward the user's working **GW-BX5600** time-sync implementation from Time Transmitter V4.16. The additional-model catalog contains **122 exact advertised names: one BX5600 model, 118 Standard protocol candidates and three experimental Analogue candidates**. This is a discovery and packet-family catalog, not a claim that 122 watches have been tested on an ESP32.

| Protocol selection | Implementation and evidence | Validation level |
| --- | --- | --- |
| GW-BX5600 MIP | Existing four-step SP handshake, model-specific TIME write and optional BX font/battery handling retained. | The user confirmed time sync on their GW-BX5600 in the original project. This new project still needs a physical acceptance test. |
| Standard digital/hybrid (experimental) | Exact model names from the pinned public implementations; corrected 11-byte `0x09` TIME command. | The encoder matches official-app DW-B5600 capture bytes. Other names are upstream protocol candidates, not new device tests. |
| Analogue (experimental) | MTG-B1000, MTG-B3000 and MTG-B3100 use the same time-only packet family. | MTG-B1000/B3000 official-app capture bytes validate the packet shape. Complete home-city/DST and second-dial setup is not implemented here. |

The catalog's Standard family includes some fully analogue watches because that is how the upstream registry classifies their packet protocol. “Standard” describes the packet family, not the type of display. `GST-B100` is classified Standard by both pinned registries; the old Time Transmitter discovery list classified it Analogue. The new exact catalog follows the reference family.

## Scope and prerequisites

CasioSync requires a watch that advertises the supported Casio BLE service and exposes the required writable TIME characteristic. Discovery uses an exact advertised model name with an optional `CASIO ` prefix. A generic service UUID, a similar model name or an unknown name cannot select the Standard/Analogue path. Retail colour suffixes such as `-1A` are not inferred; the table lists BLE advertised names. An explicitly nameless advertisement is accepted only for an already-bound BX profile whose saved address matches; new pairing requires an identified catalog name. The runtime GATT checks still apply, and a named unknown watch cannot use this exception.

The Standard/Analogue implementation sends **current civil time in the selected BT timezone**. It does not configure home cities, DST rules, world-time cities, alarms, timers, reminders or analogue dial calibration as part of the ordinary time-only operation. A watch that requires those initialization steps may reject the command or show a different result. Configure its home city/DST consistently, and treat these candidates as experimental until a real-device log and displayed-time check confirm the model. Additional optional features, where offered, require their own model-specific validation; catalog membership alone does not establish feature compatibility.

Automatic scheduling opens an ESP32 listening window. The watch must initiate BLE at that time and must have automatic time adjustment enabled; the ESP32 cannot wake a disconnected watch. The listening schedule uses the selected **BT timezone/offset**, independently of the daily Wi-Fi access schedule. Manual sync remains useful for initial model validation. A delivered/acknowledged ATT write is transport evidence; it does not independently verify the watch display.

Font changes and the battery calibration inherited from Time Transmitter remain restricted to identified **GW-BX5600** watches. Other models do not receive BX settings packets or the BX battery conversion.

## Exact Standard protocol candidates

Every name below appears in the pinned upstream exact-model map. Many entries use its generic Standard fallback; that metadata is weaker evidence than a captured successful transaction. The exact name list intentionally remains narrower than “all Casio Bluetooth watches.”

| Advertised family | Advertised model names |
| --- | --- |
| ABL | `ABL-100`, `ABL-100WE` |
| BSA | `BSA-B100` |
| DW | `DW-B5600` |
| ECB | `ECB-10`, `ECB-20`, `ECB-2000`, `ECB-2200`, `ECB-2300`, `ECB-30`, `ECB-40`, `ECB-500`, `ECB-800`, `ECB-900`, `ECB-950`, `ECB-S10`, `ECB-S100` |
| EQB | `EQB-1000`, `EQB-1100`, `EQB-1200`, `EQB-1300`, `EQB-2000`, `EQB-500`, `EQB-501`, `EQB-510`, `EQB-600`, `EQB-700`, `EQB-800`, `EQB-900` |
| F | `F-B100W` |
| G | `G-B001` |
| GA | `GA-B001`, `GA-B010`, `GA-B2100` |
| GBA | `GBA-400`, `GBA-800`, `GBA-900`, `GBA-950` |
| GBD | `GBD-800` |
| GBM | `GBM-2100` |
| GCW | `GCW-B5000` |
| GD | `GD-B500` |
| GG | `GG-B100`, `GG-B100X` |
| GM | `GM-B2100` |
| GMA | `GMA-B800` |
| GMC | `GMC-B100`, `GMC-B2100` |
| GMD | `GMD-B300`, `GMD-B800` |
| GMW | `GMW-B5000`, `GMW-B5000#`, `GMW-BZ5000` |
| GPR | `GPR-B1000` |
| GPW | `GPW-2000`, `GPW-G2000` |
| GR | `GR-B100`, `GR-B200`, `GR-B300` |
| GST | `GST-B100`, `GST-B1000`, `GST-B200`, `GST-B300`, `GST-B400`, `GST-B500`, `GST-B600`, `GST-W1000` |
| GW | `GW-B5000`, `GW-B5600`, `GW-B5600#` |
| GWF | `GWF-300`, `GWF-A1000` |
| GWG | `GWG-B1000` |
| GWR | `GWR-B1000`, `GWR-B3000` |
| LIW | `LIW-B1000` |
| MRG | `MRG-B1000`, `MRG-B2000`, `MRG-B2100`, `MRG-B5000`, `MRG-B5000#`, `MRG-BF1000`, `MRG-G2000` |
| MSG | `MSG-B100` |
| MTG | `MTG-B2000`, `MTG-B4000` |
| OCW | `OCW-5700`, `OCW-5800`, `OCW-B1200`, `OCW-B1300`, `OCW-B1400`, `OCW-G2000`, `OCW-P2000`, `OCW-P3000`, `OCW-S400`, `OCW-S4000`, `OCW-S5000`, `OCW-S6000`, `OCW-S7000`, `OCW-SG1000`, `OCW-T200`, `OCW-T3000`, `OCW-T4000`, `OCW-T4000A`, `OCW-T4000B`, `OCW-T4000C`, `OCW-T5000`, `OCW-T6000` |
| PRJ | `PRJ-B001`, `PRJ-BW002` |
| PRT | `PRT-B50`, `PRT-B70` |
| PRW | `PRW-B1000` |
| SHB | `SHB-100`, `SHB-200` |
| STB | `STB-1000` |
| TRN | `TRN-50` |
| WS | `WS-B1000` |

## Deferred models

These upstream-listed models are deliberately excluded from automatic pairing in V0.1 pending their connection lifecycle and initialization work:

- Health/other MIP or continuous-connection families: `GBD-H1000`, `GBD-H2000`, `GSR-H1000`, `GPR-H1000`, `DW-GH5600`, `DW-H5600`, `GM-H5600`, `GBX-H5600`, `GDG-B100`, `GBD-100`, `GBD-200`, `GBD-300`, `GBX-100`. The public API may support some functions on these watches, but its richer initialization/connection handling is not implemented by CasioSync's inherited time-only client. A MIP display does not imply the GW-BX5600 SP handshake.
- Earlier GB connection generations: `GB-5600A`, `GB-5600B`, `GB-6900A`, `GB-6900B`, `GB-X6900B`. The upstream name registry does not establish compatibility with this project's vendor-service/time-only workflow.
- Unknown names, other BX/MIP models, non-Bluetooth radio-only watches and Wear OS watches. No substring or unknown-model Standard fallback is enabled.

Some later watches, including `GMW-BZ5000`, are listed as Standard candidates because the pinned registry explicitly maps them to that protocol; they are not inferred to use the BX handshake. Their display and optional settings need separate device validation.

## Packet validation and reference discrepancies

Standard TIME is **11 bytes**: command `09`, little-endian year, month, day, hour, minute, second, weekday, fractional second and trailing flag `01`. The old Standard/Analogue time-only implementation sent ten bytes, omitting the fractional field; CasioSync fixes that shape without changing the working BX transaction.

Official-app captures show **Sunday=0** weekdays. For example, `btsnoop_hci-DW-B5600.log` record 6944 contains `09ea070106152104024501` for Tuesday 6 January 2026 (weekday byte `02`); `btsnoop_hci_mgt_b1000.log` record 902 contains `09ea07060f13250f018c01` for Monday 15 June (weekday `01`); and `btsnoop_hci_mgt_b3000.log` record 709 contains `09ea070715151407021701` for Tuesday 21 July (weekday `02`). The pinned web app agrees with Sunday=0. The pinned Python encoder instead uses Python's Monday=0 weekday, so CasioSync follows the real captures rather than copying that discrepancy.

The fractional field uses `floor(microseconds * 256 / 1,000,000)`, following the pinned Python TIME encoder. The pinned Standard web encoder assigns milliseconds into a byte instead; the references disagree here too. Capture vectors verify the field's position and packet length, while a complete sweep of the production encoder verifies the stated 1/256-second conversion. Capture timestamps do not reveal the original application time sample, so they do not independently prove subsecond accuracy. Physical watch testing remains necessary.

The new fixed-size headers allocate no heap, add no callbacks/tasks or flash writes, check sample ranges before modifying output, and bound advertised-name inspection to 64 bytes. Focused ASan/UBSan checks cover all 122 names, prefix/suffix confusion, malformed lengths, embedded NUL/control bytes, 100,000 generated names, literal capture vectors, invalid dates and all one million microsecond values. Those checks validate host code and packet construction, not radio reception or a physical watch's response.

## Pinned public sources

- [izivkov/gshock_api exact watch registry](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/watch_info.py), commit `ae817310dd9551d5e6e53ee61d89af4e8d954767`.
- [Python Standard protocol](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/protocols/standard_protocol.py), [Analogue protocol](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/protocols/analogue_protocol.py), and [TIME encoder](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/src/gshock_api/iolib/time_io.py).
- [Official-app DW-B5600 capture](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/test_data/btsnoop_hci-DW-B5600.log), [MTG-B1000 capture](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/test_data/btsnoop_hci_mgt_b1000.log), [MTG-B3000 capture](https://github.com/izivkov/gshock_api/blob/ae817310dd9551d5e6e53ee61d89af4e8d954767/test_data/btsnoop_hci_mgt_b3000.log).
- [gshock-smart-sync-webapp watch registry](https://github.com/izivkov/gshock-smart-sync-webapp/blob/5b3ff83dbae43a7a526232e5f35de98425ca7ac8/src/api/WatchInfo.ts) and [TIME encoder](https://github.com/izivkov/gshock-smart-sync-webapp/blob/5b3ff83dbae43a7a526232e5f35de98425ca7ac8/src/api/io/TimeIO.ts), commit `5b3ff83dbae43a7a526232e5f35de98425ca7ac8`.

The original projects' credits and licenses remain in this repository. The classifier and bounded Standard TIME helper are independently implemented from the published names, wire format and captures. Future model additions should retain an exact advertised name, the relevant service/characteristic schema, captured successful packets and a real-watch result before being described as device validated.
