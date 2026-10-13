#include "../firmware/CasioSync_V0_1/CasioStandardProtocol.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <ctime>
#include <cstring>
#include <iostream>
#include <limits>

namespace {
struct GuardedPacket {
  uint8_t before = 0xa5;
  uint8_t bytes[CasioStandardProtocol::PacketSize] = {};
  uint8_t after = 0x5a;
};

std::tm civil(int year, int month, int day, int hour, int minute, int second, int weekday) {
  std::tm value{};
  value.tm_year = year - 1900;
  value.tm_mon = month - 1;
  value.tm_mday = day;
  value.tm_hour = hour;
  value.tm_min = minute;
  value.tm_sec = second;
  value.tm_wday = weekday;
  return value;
}

void expect(const std::tm &value, int32_t usec, const std::array<uint8_t, 11> &expected) {
  GuardedPacket packet;
  assert(CasioStandardProtocol::encode(value, usec, packet.bytes));
  assert(std::equal(expected.begin(), expected.end(), packet.bytes));
  assert(packet.before == 0xa5 && packet.after == 0x5a);
}

void captures() {
  // Literal TIME payloads from official-app HCI captures in izivkov/gshock_api,
  // ae817310dd9551d5e6e53ee61d89af4e8d954767, records counted from one.
  // Fraction inputs below are chosen to reproduce the captured fraction byte;
  // the capture does not reveal the app's original microsecond sample.
  // btsnoop_hci-DW-B5600.log record 6944: Tue 2026-01-06, weekday byte 2.
  expect(civil(2026,1,6,21,33,4,2),269532,
         {0x09,0xea,0x07,0x01,0x06,0x15,0x21,0x04,0x02,0x45,0x01});
  // btsnoop_hci_mgt_b1000.log record 902: Mon 2026-06-15, weekday byte 1.
  expect(civil(2026,6,15,19,37,15,1),546875,
         {0x09,0xea,0x07,0x06,0x0f,0x13,0x25,0x0f,0x01,0x8c,0x01});
  // btsnoop_hci_mgt_b3000.log record 709: Tue 2026-07-21, weekday byte 2.
  expect(civil(2026,7,21,21,20,7,2),89844,
         {0x09,0xea,0x07,0x07,0x15,0x15,0x14,0x07,0x02,0x17,0x01});
}

void civilTimezoneAndFractions() {
  // Civil sample is already converted to selected BT timezone by the caller.
  // UTC 08:30 -> Brisbane 18:30: the encoder never applies a second offset.
  expect(civil(2026,10,13,18,30,0,2),500000,
         {0x09,0xea,0x07,0x0a,0x0d,0x12,0x1e,0x00,0x02,0x80,0x01});
  expect(civil(2026,10,11,0,0,0,0),0,
         {0x09,0xea,0x07,0x0a,0x0b,0x00,0x00,0x00,0x00,0x00,0x01});
  expect(civil(2026,10,10,23,59,59,6),999999,
         {0x09,0xea,0x07,0x0a,0x0a,0x17,0x3b,0x3b,0x06,0xff,0x01});
  GuardedPacket packet;
  const auto base = civil(2026,10,13,18,30,0,2);
  for (int32_t usec = 0; usec < 1000000; ++usec) {
    assert(CasioStandardProtocol::encode(base, usec, packet.bytes));
    // 64-bit independent scale oracle at every microsecond transition.
    assert(packet.bytes[9] == static_cast<uint8_t>((int64_t(usec) * 256) / 1000000));
    assert(packet.bytes[10] == 1 && packet.before == 0xa5 && packet.after == 0x5a);
  }
}

void reject(const std::tm &value, int32_t usec) {
  GuardedPacket packet;
  std::fill(std::begin(packet.bytes),std::end(packet.bytes),0xcc);
  assert(!CasioStandardProtocol::encode(value,usec,packet.bytes));
  assert(std::all_of(std::begin(packet.bytes),std::end(packet.bytes),[](uint8_t b){return b == 0xcc;}));
  assert(packet.before == 0xa5 && packet.after == 0x5a);
}

void invalidSamples() {
  const auto base = civil(2026,10,13,18,30,0,2);
  reject(base,-1); reject(base,1000000); reject(base,std::numeric_limits<int32_t>::max());
  auto sample = base;
  sample.tm_year = std::numeric_limits<int>::min(); reject(sample,0);
  sample.tm_year = std::numeric_limits<int>::max(); reject(sample,0);
  for (int year : {99,200}) { sample=base; sample.tm_year=year; reject(sample,0); }
  for (int month : {-1,12}) { sample=base; sample.tm_mon=month; reject(sample,0); }
  for (int day : {0,32}) { sample=base; sample.tm_mday=day; reject(sample,0); }
  for (int hour : {-1,24}) { sample=base; sample.tm_hour=hour; reject(sample,0); }
  for (int minute : {-1,60}) { sample=base; sample.tm_min=minute; reject(sample,0); }
  for (int second : {-1,60}) { sample=base; sample.tm_sec=second; reject(sample,0); }
  for (int day : {-1,7}) { sample=base; sample.tm_wday=day; reject(sample,0); }
  reject(civil(2026,2,29,0,0,0,0),0);
  reject(civil(2026,4,31,0,0,0,0),0);
  expect(civil(2000,2,29,0,0,0,2),0,
         {0x09,0xd0,0x07,0x02,0x1d,0x00,0x00,0x00,0x02,0x00,0x01});
  expect(civil(2099,12,31,23,59,59,4),0,
         {0x09,0x33,0x08,0x0c,0x1f,0x17,0x3b,0x3b,0x04,0x00,0x01});
}
}

int main() {
  static_assert(CasioStandardProtocol::PacketSize == 11,"Captured standard TIME is 11 bytes");
  captures(); civilTimezoneAndFractions(); invalidSamples();
  std::cout << "Standard TIME: official DW/MTG capture vectors, civil timezone, all fractions and invalid samples passed\n";
}
