#pragma once

#include <stddef.h>
#include <stdint.h>

// CasioSync V0.1: exact advertised-name protocol candidates. A known name is
// not device validation; the caller must still check the Casio GATT schema.
// Reference: izivkov/gshock_api ae817310 / watch_info.py (see WATCH_SUPPORT.md).
// All storage is immutable and bounded. No Arduino String, allocation or I/O.
namespace CasioModelCatalog {

enum class Protocol : uint8_t { Bx5600 = 0, Standard = 1, Analogue = 2, Unknown = 255 };

struct Entry {
  const char *model;
  Protocol protocol;
};

struct Match {
  const char *model;
  Protocol protocol;
  bool automatic; // Eligible for this explicitly selected protocol's discovery.
};

static const Entry Models[] = {
  {"ABL-100", Protocol::Standard},
  {"ABL-100WE", Protocol::Standard},
  {"BSA-B100", Protocol::Standard},
  {"DW-B5600", Protocol::Standard},
  {"ECB-10", Protocol::Standard},
  {"ECB-20", Protocol::Standard},
  {"ECB-2000", Protocol::Standard},
  {"ECB-2200", Protocol::Standard},
  {"ECB-2300", Protocol::Standard},
  {"ECB-30", Protocol::Standard},
  {"ECB-40", Protocol::Standard},
  {"ECB-500", Protocol::Standard},
  {"ECB-800", Protocol::Standard},
  {"ECB-900", Protocol::Standard},
  {"ECB-950", Protocol::Standard},
  {"ECB-S10", Protocol::Standard},
  {"ECB-S100", Protocol::Standard},
  {"EQB-1000", Protocol::Standard},
  {"EQB-1100", Protocol::Standard},
  {"EQB-1200", Protocol::Standard},
  {"EQB-1300", Protocol::Standard},
  {"EQB-2000", Protocol::Standard},
  {"EQB-500", Protocol::Standard},
  {"EQB-501", Protocol::Standard},
  {"EQB-510", Protocol::Standard},
  {"EQB-600", Protocol::Standard},
  {"EQB-700", Protocol::Standard},
  {"EQB-800", Protocol::Standard},
  {"EQB-900", Protocol::Standard},
  {"F-B100W", Protocol::Standard},
  {"G-B001", Protocol::Standard},
  {"GA-B001", Protocol::Standard},
  {"GA-B010", Protocol::Standard},
  {"GA-B2100", Protocol::Standard},
  {"GBA-400", Protocol::Standard},
  {"GBA-800", Protocol::Standard},
  {"GBA-900", Protocol::Standard},
  {"GBA-950", Protocol::Standard},
  {"GBD-800", Protocol::Standard},
  {"GBM-2100", Protocol::Standard},
  {"GCW-B5000", Protocol::Standard},
  {"GD-B500", Protocol::Standard},
  {"GG-B100", Protocol::Standard},
  {"GG-B100X", Protocol::Standard},
  {"GM-B2100", Protocol::Standard},
  {"GMA-B800", Protocol::Standard},
  {"GMC-B100", Protocol::Standard},
  {"GMC-B2100", Protocol::Standard},
  {"GMD-B300", Protocol::Standard},
  {"GMD-B800", Protocol::Standard},
  {"GMW-B5000", Protocol::Standard},
  {"GMW-B5000#", Protocol::Standard},
  {"GMW-BZ5000", Protocol::Standard},
  {"GPR-B1000", Protocol::Standard},
  {"GPW-2000", Protocol::Standard},
  {"GPW-G2000", Protocol::Standard},
  {"GR-B100", Protocol::Standard},
  {"GR-B200", Protocol::Standard},
  {"GR-B300", Protocol::Standard},
  {"GST-B100", Protocol::Standard},
  {"GST-B1000", Protocol::Standard},
  {"GST-B200", Protocol::Standard},
  {"GST-B300", Protocol::Standard},
  {"GST-B400", Protocol::Standard},
  {"GST-B500", Protocol::Standard},
  {"GST-B600", Protocol::Standard},
  {"GST-W1000", Protocol::Standard},
  {"GW-B5000", Protocol::Standard},
  {"GW-B5600", Protocol::Standard},
  {"GW-B5600#", Protocol::Standard},
  {"GW-BX5600", Protocol::Bx5600},
  {"GWF-300", Protocol::Standard},
  {"GWF-A1000", Protocol::Standard},
  {"GWG-B1000", Protocol::Standard},
  {"GWR-B1000", Protocol::Standard},
  {"GWR-B3000", Protocol::Standard},
  {"LIW-B1000", Protocol::Standard},
  {"MRG-B1000", Protocol::Standard},
  {"MRG-B2000", Protocol::Standard},
  {"MRG-B2100", Protocol::Standard},
  {"MRG-B5000", Protocol::Standard},
  {"MRG-B5000#", Protocol::Standard},
  {"MRG-BF1000", Protocol::Standard},
  {"MRG-G2000", Protocol::Standard},
  {"MSG-B100", Protocol::Standard},
  {"MTG-B1000", Protocol::Analogue},
  {"MTG-B2000", Protocol::Standard},
  {"MTG-B3000", Protocol::Analogue},
  {"MTG-B3100", Protocol::Analogue},
  {"MTG-B4000", Protocol::Standard},
  {"OCW-5700", Protocol::Standard},
  {"OCW-5800", Protocol::Standard},
  {"OCW-B1200", Protocol::Standard},
  {"OCW-B1300", Protocol::Standard},
  {"OCW-B1400", Protocol::Standard},
  {"OCW-G2000", Protocol::Standard},
  {"OCW-P2000", Protocol::Standard},
  {"OCW-P3000", Protocol::Standard},
  {"OCW-S400", Protocol::Standard},
  {"OCW-S4000", Protocol::Standard},
  {"OCW-S5000", Protocol::Standard},
  {"OCW-S6000", Protocol::Standard},
  {"OCW-S7000", Protocol::Standard},
  {"OCW-SG1000", Protocol::Standard},
  {"OCW-T200", Protocol::Standard},
  {"OCW-T3000", Protocol::Standard},
  {"OCW-T4000", Protocol::Standard},
  {"OCW-T4000A", Protocol::Standard},
  {"OCW-T4000B", Protocol::Standard},
  {"OCW-T4000C", Protocol::Standard},
  {"OCW-T5000", Protocol::Standard},
  {"OCW-T6000", Protocol::Standard},
  {"PRJ-B001", Protocol::Standard},
  {"PRJ-BW002", Protocol::Standard},
  {"PRT-B50", Protocol::Standard},
  {"PRT-B70", Protocol::Standard},
  {"PRW-B1000", Protocol::Standard},
  {"SHB-100", Protocol::Standard},
  {"SHB-200", Protocol::Standard},
  {"STB-1000", Protocol::Standard},
  {"TRN-50", Protocol::Standard},
  {"WS-B1000", Protocol::Standard},
};

static const size_t ModelCount = sizeof(Models) / sizeof(Models[0]);
static const size_t MaximumAdvertisementLength = 64;

inline char asciiUpper(char value) {
  return value >= 'a' && value <= 'z' ? static_cast<char>(value - ('a' - 'A')) : value;
}

inline bool isSpace(char value) { return value == ' ' || value == '\t'; }

inline Match classify(const char *name, size_t length) {
  const Match unknown = {nullptr, Protocol::Unknown, false};
  if (!name || !length || length > MaximumAdvertisementLength) return unknown;
  // Explicit lengths prevent walking past a BLE name buffer. Embedded NUL and
  // other control/non-ASCII bytes cannot alias a valid advertised model.
  for (size_t i = 0; i < length; ++i) {
    const uint8_t value = static_cast<uint8_t>(name[i]);
    if ((value < 0x20 && value != '\t') || value > 0x7e) return unknown;
  }
  size_t begin = 0;
  size_t end = length;
  while (begin < end && isSpace(name[begin])) ++begin;
  while (end > begin && isSpace(name[end - 1])) --end;
  if (end - begin >= 6 && asciiUpper(name[begin]) == 'C' &&
      asciiUpper(name[begin + 1]) == 'A' && asciiUpper(name[begin + 2]) == 'S' &&
      asciiUpper(name[begin + 3]) == 'I' && asciiUpper(name[begin + 4]) == 'O' &&
      isSpace(name[begin + 5])) {
    begin += 6;
    while (begin < end && isSpace(name[begin])) ++begin;
  }
  if (begin == end) return unknown;
  for (size_t modelIndex = 0; modelIndex < ModelCount; ++modelIndex) {
    const Entry &entry = Models[modelIndex];
    size_t index = 0;
    while (index < end - begin && entry.model[index] &&
           asciiUpper(name[begin + index]) == entry.model[index]) ++index;
    if (index == end - begin && entry.model[index] == '\0') {
      const Match match = {entry.model, entry.protocol, true};
      return match;
    }
  }
  return unknown;
}

inline bool matches(Protocol protocol, const char *name, size_t length) {
  if (protocol == Protocol::Unknown) return false;
  const Match match = classify(name, length);
  return match.automatic && match.protocol == protocol;
}

} // namespace CasioModelCatalog
