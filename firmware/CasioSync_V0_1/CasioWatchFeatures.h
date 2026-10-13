#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "CasioModelCatalog.h"

// Independently implemented from the public gshock_api and Smart Sync web app:
// gshock_api ae817310dd9551d5e6e53ee61d89af4e8d954767 / iolib/{alarms,timer,settings,time_adjustment}_io.py
// gshock-smart-sync-webapp 5b3ff83dbae43a7a526232e5f35de98425ca7ac8 / src/api/io/*IO.ts
// Always merge an actual, validated watch reply. Never manufacture a complete
// settings packet or assume the SP_DATA "alarm" time-handshake stage contains
// real alarms: those records are city names and remain untouched.
namespace CasioWatchFeatures {

constexpr uint8_t kFirstAlarmHeader = 0x15;
constexpr uint8_t kOtherAlarmsHeader = 0x16;
constexpr uint8_t kTimerHeader = 0x18;
constexpr uint8_t kBasicHeader = 0x13;
constexpr uint8_t kAutoAdjustHeader = 0x11;
constexpr size_t kMaxPacketSize = 17;
constexpr size_t kAlarmCount = 5;
constexpr uint8_t kTimeFormat = 0x01;
constexpr uint8_t kButtonTone = 0x02;
constexpr uint8_t kAutoLight = 0x04;
constexpr uint8_t kPowerSaving = 0x08;
constexpr uint8_t kLightDuration = 0x10;
constexpr uint8_t kDateFormat = 0x20;
constexpr uint8_t kLanguage = 0x40;
constexpr uint8_t kAllBasic = 0x7f;

struct Alarm {
  bool enabled = false;
  uint8_t hour = 6;
  uint8_t minute = 30;
};

struct Desired {
  bool enabled = false;
  bool alarmsEnabled = false;
  Alarm alarms[kAlarmCount];
  int8_t hourlyChime = -1; // Keep (-1), off (0), on (1).
  bool timerEnabled = false;
  uint32_t timerSeconds = 300;
  uint8_t basicMask = 0; // Unset bit means "Keep watch setting".
  bool timeFormat24 = true;
  bool buttonTone = true;
  bool autoLight = false;
  bool powerSaving = true;
  bool longLight = false;
  bool dateDayFirst = false;
  uint8_t language = 0; // English, Spanish, French, German, Italian, Russian.
  bool autoAdjustEnabled = false;
  bool autoAdjust = true;
  uint8_t autoAdjustMinute = 30; // Minute AFTER THE HOUR, not minutes of day.
};

struct Caps {
  uint8_t alarmCount = 0;
  uint8_t basicMask = 0;
  bool hourlyChime = false;
  bool timer = false;
  bool autoAdjust = false;
  uint32_t timerMaxSeconds = 0;
};

// Exact-name feature candidates derived from the pinned ModelInfo registry.
// No candidate is a hardware-validation claim. Runtime reply shape and
// explicit per-feature readback are required before reporting confirmation.
// Non-square timer limits are conservatively restricted to one hour until
// their model-specific maximum is evidenced; digital-square maximum is 24h.
inline Caps capabilities(const char *name, size_t length) {
  Caps none;
  const CasioModelCatalog::Match match = CasioModelCatalog::classify(name, length);
  if (!match.model || !match.automatic ||
      (match.protocol != CasioModelCatalog::Protocol::Bx5600 &&
       match.protocol != CasioModelCatalog::Protocol::Standard)) return none;
  struct Entry { const char *model; uint8_t alarmCount; uint8_t basicMask;
                 bool chime; bool automatic; uint32_t timerMaximum; };
  static const Entry entries[] = {
    {"ABL-100", 5, 0x1b, true, true, 3600},
    {"ABL-100WE", 5, 0x1b, true, true, 3600},
    {"BSA-B100", 5, 0x7b, true, true, 3600},
    {"DW-B5600", 5, 0x7b, true, true, 86400},
    {"ECB-10", 5, 0x77, true, true, 3600},
    {"ECB-20", 5, 0x77, true, true, 3600},
    {"ECB-2000", 5, 0x77, true, true, 3600},
    {"ECB-2200", 5, 0x77, true, true, 3600},
    {"ECB-2300", 5, 0x77, true, true, 3600},
    {"ECB-30", 5, 0x77, true, true, 3600},
    {"ECB-40", 5, 0x77, true, true, 3600},
    {"ECB-500", 5, 0x77, true, true, 3600},
    {"ECB-800", 5, 0x77, true, true, 3600},
    {"ECB-900", 5, 0x7b, true, true, 3600},
    {"ECB-950", 5, 0x7b, true, true, 3600},
    {"ECB-S10", 5, 0x77, true, true, 3600},
    {"ECB-S100", 5, 0x77, true, true, 3600},
    {"EQB-1000", 5, 0x7f, true, true, 3600},
    {"EQB-1100", 5, 0x7f, true, true, 3600},
    {"EQB-1200", 5, 0x7f, true, true, 3600},
    {"EQB-1300", 5, 0x7f, true, true, 3600},
    {"EQB-2000", 5, 0x7f, true, true, 3600},
    {"EQB-500", 5, 0x7f, true, true, 3600},
    {"EQB-501", 5, 0x7f, true, true, 3600},
    {"EQB-510", 5, 0x7f, true, true, 3600},
    {"EQB-600", 5, 0x7f, true, true, 3600},
    {"EQB-700", 5, 0x7f, true, true, 3600},
    {"EQB-800", 5, 0x7f, true, true, 3600},
    {"EQB-900", 5, 0x7f, true, true, 3600},
    {"F-B100W", 5, 0x1b, true, true, 3600},
    {"G-B001", 5, 0x7f, true, true, 3600},
    {"GA-B001", 5, 0x7b, true, true, 3600},
    {"GA-B010", 5, 0x7b, true, true, 3600},
    {"GA-B2100", 5, 0x7b, true, true, 3600},
    {"GBA-400", 5, 0x7b, true, true, 3600},
    {"GBA-800", 5, 0x7b, true, true, 3600},
    {"GBA-900", 5, 0x7b, true, true, 3600},
    {"GBA-950", 5, 0x7b, true, true, 3600},
    {"GBD-800", 5, 0x7f, true, true, 3600},
    {"GBM-2100", 5, 0x7b, true, true, 3600},
    {"GCW-B5000", 5, 0x7f, true, true, 86400},
    {"GD-B500", 5, 0x7b, true, true, 3600},
    {"GG-B100", 5, 0x7b, true, true, 3600},
    {"GG-B100X", 5, 0x7b, true, true, 3600},
    {"GM-B2100", 5, 0x7b, true, true, 3600},
    {"GMA-B800", 5, 0x7b, true, true, 3600},
    {"GMC-B100", 5, 0x7b, true, true, 3600},
    {"GMC-B2100", 5, 0x7b, true, true, 3600},
    {"GMD-B300", 5, 0x7b, true, true, 3600},
    {"GMD-B800", 5, 0x7f, true, true, 3600},
    {"GMW-B5000", 5, 0x7f, true, true, 86400},
    {"GMW-B5000#", 5, 0x7f, true, true, 86400},
    {"GMW-BZ5000", 5, 0x7f, true, true, 86400},
    {"GPR-B1000", 5, 0x3f, true, true, 3600},
    {"GPW-2000", 5, 0x7b, true, true, 3600},
    {"GPW-G2000", 5, 0x7b, true, true, 3600},
    {"GR-B100", 5, 0x7b, true, true, 3600},
    {"GR-B200", 5, 0x7b, true, true, 3600},
    {"GR-B300", 5, 0x7b, true, true, 3600},
    {"GST-B100", 5, 0x7b, true, true, 3600},
    {"GST-B1000", 5, 0x7b, true, true, 3600},
    {"GST-B200", 5, 0x7b, true, true, 3600},
    {"GST-B300", 5, 0x7b, true, true, 3600},
    {"GST-B400", 5, 0x7b, true, true, 3600},
    {"GST-B500", 5, 0x7b, true, true, 3600},
    {"GST-B600", 5, 0x7b, true, true, 3600},
    {"GST-W1000", 5, 0x7b, true, true, 3600},
    {"GW-B5000", 5, 0x7f, true, true, 86400},
    {"GW-B5600", 5, 0x7f, true, true, 86400},
    {"GW-B5600#", 5, 0x7f, true, true, 86400},
    {"GW-BX5600", 5, 0x7f, true, true, 86400},
    {"GWF-300", 5, 0x7b, true, true, 3600},
    {"GWF-A1000", 5, 0x7b, true, true, 3600},
    {"GWG-B1000", 5, 0x7f, true, true, 3600},
    {"GWR-B1000", 5, 0x7f, true, true, 3600},
    {"GWR-B3000", 5, 0x7f, true, true, 3600},
    {"LIW-B1000", 5, 0x7b, true, true, 3600},
    {"MRG-B1000", 5, 0x7b, true, true, 3600},
    {"MRG-B2000", 5, 0x7b, true, true, 3600},
    {"MRG-B2100", 5, 0x7b, true, true, 3600},
    {"MRG-B5000", 5, 0x7f, true, true, 86400},
    {"MRG-B5000#", 5, 0x7f, true, true, 86400},
    {"MRG-BF1000", 5, 0x7b, true, true, 3600},
    {"MRG-G2000", 5, 0x7b, true, true, 3600},
    {"MSG-B100", 5, 0x7b, true, true, 3600},
    {"MTG-B2000", 5, 0x7b, true, true, 3600},
    {"MTG-B4000", 5, 0x7b, true, true, 3600},
    {"OCW-5700", 5, 0x7b, true, true, 3600},
    {"OCW-5800", 5, 0x7b, true, true, 3600},
    {"OCW-B1200", 5, 0x7b, true, true, 3600},
    {"OCW-B1300", 5, 0x7b, true, true, 3600},
    {"OCW-B1400", 5, 0x7b, true, true, 3600},
    {"OCW-G2000", 5, 0x7b, true, true, 3600},
    {"OCW-P2000", 5, 0x7b, true, true, 3600},
    {"OCW-P3000", 5, 0x7b, true, true, 3600},
    {"OCW-S400", 5, 0x7b, true, true, 3600},
    {"OCW-S4000", 5, 0x7b, true, true, 3600},
    {"OCW-S5000", 5, 0x7b, true, true, 3600},
    {"OCW-S6000", 5, 0x7b, true, true, 3600},
    {"OCW-S7000", 5, 0x7b, true, true, 3600},
    {"OCW-SG1000", 5, 0x7b, true, true, 3600},
    {"OCW-T200", 5, 0x7b, true, true, 3600},
    {"OCW-T3000", 5, 0x7b, true, true, 3600},
    {"OCW-T4000", 5, 0x7b, true, true, 3600},
    {"OCW-T4000A", 5, 0x7b, true, true, 3600},
    {"OCW-T4000B", 5, 0x7b, true, true, 3600},
    {"OCW-T4000C", 5, 0x7b, true, true, 3600},
    {"OCW-T5000", 5, 0x7b, true, true, 3600},
    {"OCW-T6000", 5, 0x7b, true, true, 3600},
    {"PRJ-B001", 5, 0x7f, true, true, 3600},
    {"PRJ-BW002", 5, 0x7f, true, true, 86400},
    {"PRT-B50", 5, 0x7b, true, true, 3600},
    {"PRT-B70", 5, 0x7b, true, true, 3600},
    {"PRW-B1000", 5, 0x7b, true, true, 3600},
    {"SHB-100", 5, 0x7b, true, true, 3600},
    {"SHB-200", 5, 0x7b, true, true, 3600},
    {"STB-1000", 5, 0x7b, true, true, 3600},
    {"TRN-50", 5, 0x7f, true, true, 86400},
    {"WS-B1000", 5, 0x7b, true, true, 3600},
  };
  for (size_t i = 0; i < sizeof(entries) / sizeof(entries[0]); ++i) {
    if (strcmp(match.model, entries[i].model) != 0) continue;
    Caps caps;
    caps.alarmCount = entries[i].alarmCount;
    caps.basicMask = entries[i].basicMask;
    caps.hourlyChime = entries[i].chime;
    caps.timer = true;
    caps.autoAdjust = entries[i].automatic;
    caps.timerMaxSeconds = entries[i].timerMaximum;
    return caps;
  }
  return none;
}

inline bool validDesired(const Desired &d) {
  if (d.hourlyChime < -1 || d.hourlyChime > 1 ||
      (d.basicMask & ~kAllBasic) || d.language > 5 ||
      d.autoAdjustMinute > 59 || d.timerSeconds < 1 || d.timerSeconds > 86400) return false;
  for (size_t i = 0; i < kAlarmCount; ++i) {
    if (d.alarms[i].hour > 23 || d.alarms[i].minute > 59) return false;
  }
  return true;
}

inline bool validFirstAlarm(const uint8_t *reply, size_t size) {
  return reply && size == 5 && reply[0] == kFirstAlarmHeader &&
         reply[3] <= 23 && reply[4] <= 59;
}

inline bool validOtherAlarms(const uint8_t *reply, size_t size, uint8_t alarmCount) {
  if (!reply || alarmCount < 2 || alarmCount > kAlarmCount ||
      size != 1 + 4U * (alarmCount - 1U) || reply[0] != kOtherAlarmsHeader) return false;
  for (size_t i = 1; i < alarmCount; ++i) {
    const size_t offset = 1 + (i - 1) * 4;
    if (reply[offset + 2] > 23 || reply[offset + 3] > 59) return false;
  }
  return true;
}

inline bool validTimer(const uint8_t *reply, size_t size) {
  // The API/web encoders disagree about six versus seven bytes; a captured
  // BX reply has fifteen. Keep the watch's actual shape and all trailing bytes.
  return reply && (size == 6 || size == 7 || size == 15) &&
         reply[0] == kTimerHeader && reply[1] <= 24 && reply[2] <= 59 && reply[3] <= 59 &&
         (reply[1] != 24 || (reply[2] == 0 && reply[3] == 0));
}

inline bool validBasic(const uint8_t *reply, size_t size) {
  return reply && (size == 12 || size == 17) && reply[0] == kBasicHeader;
}

inline bool validAutoAdjust(const uint8_t *reply, size_t size) {
  return reply && size == 15 && reply[0] == kAutoAdjustHeader && reply[13] <= 59;
}

inline uint8_t setBit(uint8_t original, uint8_t mask, bool enabled) {
  return enabled ? static_cast<uint8_t>(original | mask)
                 : static_cast<uint8_t>(original & ~mask);
}

// All merge functions stage their result, support in-place use, and leave the
// output untouched on every validation failure. They perform no allocation.
inline bool mergeFirstAlarm(const uint8_t *reply, size_t size, const Desired &d,
                            uint8_t *out, size_t capacity) {
  if (!out || capacity < size || !validDesired(d) || !validFirstAlarm(reply, size)) return false;
  uint8_t staged[5];
  memcpy(staged, reply, size);
  if (d.alarmsEnabled) {
    staged[1] = setBit(staged[1], 0x40, d.alarms[0].enabled);
    staged[3] = d.alarms[0].hour;
    staged[4] = d.alarms[0].minute;
  }
  if (d.hourlyChime >= 0) staged[1] = setBit(staged[1], 0x80, d.hourlyChime == 1);
  memcpy(out, staged, size);
  return true;
}

inline bool mergeOtherAlarms(const uint8_t *reply, size_t size, uint8_t alarmCount,
                            const Desired &d, uint8_t *out, size_t capacity) {
  if (!out || capacity < size || !validDesired(d) ||
      !validOtherAlarms(reply, size, alarmCount)) return false;
  uint8_t staged[kMaxPacketSize];
  memcpy(staged, reply, size);
  if (d.alarmsEnabled) {
    for (size_t i = 1; i < alarmCount; ++i) {
      const size_t offset = 1 + (i - 1) * 4;
      staged[offset] = setBit(staged[offset], 0x40, d.alarms[i].enabled);
      staged[offset + 2] = d.alarms[i].hour;
      staged[offset + 3] = d.alarms[i].minute;
    }
  }
  memcpy(out, staged, size);
  return true;
}

inline bool mergeTimer(const uint8_t *reply, size_t size, const Desired &d,
                       uint8_t *out, size_t capacity) {
  if (!out || capacity < size || !validDesired(d) || !validTimer(reply, size)) return false;
  uint8_t staged[kMaxPacketSize];
  memcpy(staged, reply, size);
  if (d.timerEnabled) {
    staged[1] = static_cast<uint8_t>(d.timerSeconds / 3600);
    staged[2] = static_cast<uint8_t>((d.timerSeconds / 60) % 60);
    staged[3] = static_cast<uint8_t>(d.timerSeconds % 60);
  }
  memcpy(out, staged, size);
  return true;
}

inline bool mergeBasic(const uint8_t *reply, size_t size, uint8_t allowedMask,
                       const Desired &d, uint8_t *out, size_t capacity) {
  if (!out || capacity < size || !validDesired(d) || !validBasic(reply, size) ||
      (d.basicMask & ~allowedMask)) return false;
  uint8_t staged[kMaxPacketSize];
  memcpy(staged, reply, size);
  if (d.basicMask & kTimeFormat) staged[1] = setBit(staged[1], 0x01, d.timeFormat24);
  if (d.basicMask & kButtonTone) {
    staged[1] = setBit(staged[1], 0x02, !d.buttonTone);
    if (size == 17) staged[12] = setBit(staged[12], 0x04, d.buttonTone);
  }
  if (d.basicMask & kAutoLight) staged[1] = setBit(staged[1], 0x04, !d.autoLight);
  if (d.basicMask & kPowerSaving) staged[1] = setBit(staged[1], 0x10, !d.powerSaving);
  if (d.basicMask & kLightDuration) staged[2] = setBit(staged[2], 0x01, d.longLight);
  if (d.basicMask & kDateFormat) staged[4] = d.dateDayFirst ? 1 : 0;
  if (d.basicMask & kLanguage) staged[5] = d.language;
  memcpy(out, staged, size);
  return true;
}

inline bool mergeAutoAdjust(const uint8_t *reply, size_t size, const Desired &d,
                            uint8_t *out, size_t capacity) {
  if (!out || capacity < size || !validDesired(d) || !validAutoAdjust(reply, size)) return false;
  uint8_t staged[kMaxPacketSize];
  memcpy(staged, reply, size);
  if (d.autoAdjustEnabled) {
    staged[12] = setBit(staged[12], 0x80, !d.autoAdjust);
    staged[13] = d.autoAdjustMinute;
  }
  memcpy(out, staged, size);
  return true;
}

// Readback compares only selected fields; reserved/status bytes may legitimately
// change during a transaction. A write acknowledgement alone is not readback.
inline bool firstAlarmMatches(const uint8_t *reply, size_t size, const Desired &d) {
  if (!validDesired(d) || !validFirstAlarm(reply, size)) return false;
  if (d.alarmsEnabled && ((bool(reply[1] & 0x40) != d.alarms[0].enabled) ||
      reply[3] != d.alarms[0].hour || reply[4] != d.alarms[0].minute)) return false;
  return d.hourlyChime < 0 || bool(reply[1] & 0x80) == (d.hourlyChime == 1);
}

inline bool otherAlarmsMatch(const uint8_t *reply, size_t size, uint8_t alarmCount,
                            const Desired &d) {
  if (!validDesired(d) || !validOtherAlarms(reply, size, alarmCount)) return false;
  if (!d.alarmsEnabled) return true;
  for (size_t i = 1; i < alarmCount; ++i) {
    const size_t offset = 1 + (i - 1) * 4;
    if (bool(reply[offset] & 0x40) != d.alarms[i].enabled ||
        reply[offset + 2] != d.alarms[i].hour || reply[offset + 3] != d.alarms[i].minute) return false;
  }
  return true;
}

inline bool timerMatches(const uint8_t *reply, size_t size, const Desired &d) {
  if (!validDesired(d) || !validTimer(reply, size)) return false;
  return !d.timerEnabled || uint32_t(reply[1]) * 3600U + uint32_t(reply[2]) * 60U + reply[3] == d.timerSeconds;
}

inline bool basicMatches(const uint8_t *reply, size_t size, uint8_t allowedMask,
                         const Desired &d) {
  uint8_t merged[kMaxPacketSize];
  if (!mergeBasic(reply, size, allowedMask, d, merged, sizeof(merged))) return false;
  // Re-merging a matching watch reply is idempotent for all selected fields.
  return memcmp(reply, merged, size) == 0;
}

inline bool autoAdjustMatches(const uint8_t *reply, size_t size, const Desired &d) {
  if (!validDesired(d) || !validAutoAdjust(reply, size)) return false;
  return !d.autoAdjustEnabled || (bool(reply[12] & 0x80) == !d.autoAdjust && reply[13] == d.autoAdjustMinute);
}

} // namespace CasioWatchFeatures
