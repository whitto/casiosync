#pragma once

#include <stdint.h>
#include <time.h>

// CasioSync V0.1 time-only Standard/Analogue encoder. The 11-byte wire shape
// and Sunday=0 weekday are present in official-app DW-B5600 and MTG captures.
// Fractional seconds use the 1/256-second field from the pinned Python TimeIO.
// The caller supplies civil time in the selected BT timezone, not UTC.
// This does not change home-city/DST settings or perform analogue dial setup.
namespace CasioStandardProtocol {

static const unsigned PacketSize = 11;

inline bool encode(const struct tm &local, int32_t microseconds,
                   uint8_t (&packet)[PacketSize]) {
  // Casio's supported civil-year range is 2000..2099. Check before arithmetic
  // or output so an invalid sample cannot produce a partly initialized write.
  if (local.tm_year < 100 || local.tm_year > 199 || local.tm_mon < 0 ||
      local.tm_mon > 11 || local.tm_mday < 1 || local.tm_hour < 0 ||
      local.tm_hour > 23 || local.tm_min < 0 || local.tm_min > 59 ||
      local.tm_sec < 0 || local.tm_sec > 59 || local.tm_wday < 0 ||
      local.tm_wday > 6 || microseconds < 0 || microseconds > 999999) return false;
  const int year = local.tm_year + 1900;
  static const uint8_t daysInMonth[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
  unsigned maxDay = daysInMonth[local.tm_mon];
  if (local.tm_mon == 1 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)) ++maxDay;
  if (static_cast<unsigned>(local.tm_mday) > maxDay) return false;

  packet[0] = 0x09;
  packet[1] = static_cast<uint8_t>(year & 0xff);
  packet[2] = static_cast<uint8_t>((year >> 8) & 0xff);
  packet[3] = static_cast<uint8_t>(local.tm_mon + 1);
  packet[4] = static_cast<uint8_t>(local.tm_mday);
  packet[5] = static_cast<uint8_t>(local.tm_hour);
  packet[6] = static_cast<uint8_t>(local.tm_min);
  packet[7] = static_cast<uint8_t>(local.tm_sec);
  packet[8] = static_cast<uint8_t>(local.tm_wday); // Sunday=0 ... Saturday=6.
  packet[9] = static_cast<uint8_t>((static_cast<uint32_t>(microseconds) * 256u) / 1000000u);
  packet[10] = 0x01;
  return true;
}

} // namespace CasioStandardProtocol
