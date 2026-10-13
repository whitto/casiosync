#!/usr/bin/env python3
"""Fault-check the compact daily history format and Brisbane write quota."""
import shutil

import re

import subprocess

import tempfile

import unittest

from pathlib import Path

import support as workflow

FIRMWARE = workflow.FIRMWARE

DRIVER = r'''
#include "BtSyncHistory.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <limits>
#include <type_traits>
#include <vector>
using namespace BtSyncHistory;
static_assert(std::is_trivial<Snapshot>::value, "Snapshot must remain plain data");
static_assert(std::is_standard_layout<Snapshot>::value, "Snapshot layout must remain fixed");
static_assert(sizeof(Snapshot) <= 192, "Persist only compact status, not textual logs");
static Snapshot sample() {
  Snapshot s{};
  s.generation = 7;
  s.successEpoch = 1791453600;  // 2026-10-08 10:00:00 UTC / 20:00 Brisbane.
  s.savedDay = brisbaneDay(s.successEpoch);
  s.lastProfile = 2; s.lastProtocol = 0;
  s.connections = 9; s.ackedWrites = 15; s.notifications = 28; s.responseErrors = 2;
  s.protocolEpoch[0] = s.profileEpoch[2] = s.successEpoch;
  std::strcpy(s.profileAddress[2], "A1:B2:C3:D4:E5:F6");
  seal(s);
  return s;
}
static void quota() {
  const int64_t midnight = 1791468000;  // 2026-10-08 14:00 UTC / Oct 9 midnight Brisbane.
  const int64_t yesterday = brisbaneDay(midnight - 1), today = brisbaneDay(midnight);
  assert(today == yesterday + 1);
  assert(brisbaneDay(midnight + 86399) == today);
  assert(brisbaneDay(midnight + 86400) == today + 1);
  assert(brisbaneDay(EarliestClockUtc - 1) == -1);
  assert(brisbaneDay(LatestClockUtc + 1) == -1);
  assert(brisbaneDay(std::numeric_limits<int64_t>::min()) == -1);
  assert(brisbaneDay(std::numeric_limits<int64_t>::max()) == -1);
  assert(!saveDue(false, midnight, -1, -1));
  assert(saveDue(true, midnight, -1, -1));
  assert(!saveDue(true, midnight + 86399, today, -1));  // Reboot: persisted quota survives.
  assert(!saveDue(true, midnight + 86399, -1, today));  // Failed attempt: no busy retry loop.
  assert(!saveDue(true, midnight - 1, today, -1));     // Clock rollback.
  assert(!saveDue(true, midnight - 1, -1, today));
  assert(saveDue(true, midnight + 86400, today, today));
  assert(!saveDue(true, 0, -1, -1));
  assert(!saveDue(true, LatestClockUtc + 1, -1, -1));
  // An Off/On setting change must keep the saved-day allowance externally.
  assert(!saveDue(true, midnight + 1, today, -1));
  std::puts("Brisbane calendar-day quota: midnight, reboot, disable/re-enable, failed attempt and clock rollback passed");
}
static void corruption() {
  const Snapshot source = sample();
  assert(valid(source));
  std::vector<unsigned char> flash(sizeof(Snapshot));
  std::memcpy(flash.data(), &source, sizeof(source));
  Snapshot restored{};
  std::memcpy(&restored, flash.data(), sizeof(restored));
  assert(valid(restored));
  assert(restored.generation == 7 && restored.connections == 9 && restored.ackedWrites == 15);
  assert(restored.profileEpoch[2] == source.successEpoch);
  assert(restored.notifications == 28 && restored.responseErrors == 2);
  assert(std::strcmp(restored.profileAddress[2], source.profileAddress[2]) == 0);
  // Every bit in every stored byte, including the CRC/header/padding, is checked.
  for (size_t byte = 0; byte < sizeof(Snapshot); ++byte) {
    for (unsigned bit = 0; bit < 8; ++bit) {
      Snapshot damaged{};
      std::memcpy(&damaged, &source, sizeof(damaged));
      reinterpret_cast<unsigned char *>(&damaged)[byte] ^= 1U << bit;
      assert(!valid(damaged));
    }
  }
  std::printf("Compact %zu-byte snapshot preserves counters, UTC timestamps and watch identity; every single-bit corruption rejected\n", sizeof(Snapshot));
}
static void validation() {
  Snapshot s = sample();
  s.magic ^= 1U; s.checksum = crc32(s); assert(!valid(s));
  s = sample(); s.schema++; s.checksum = crc32(s); assert(!valid(s));
  s = sample(); s.size--; s.checksum = crc32(s); assert(!valid(s));
  s = sample(); s.savedDay++; seal(s); assert(!valid(s));
  s = sample(); s.successEpoch = EarliestClockUtc - 1; s.savedDay = -1; seal(s); assert(!valid(s));
  s = sample(); s.successEpoch = LatestClockUtc + 1; s.savedDay = -1; seal(s); assert(!valid(s));
  s = sample(); s.lastProfile = ProfileCount; seal(s); assert(!valid(s));
  s = sample(); s.lastProtocol = ProtocolCount; seal(s); assert(!valid(s));
  s = sample(); std::memset(s.profileAddress[2], 'x', sizeof(s.profileAddress[2])); seal(s); assert(!valid(s));
  s = sample(); s.profileAddress[2][2] = '-'; seal(s); assert(!valid(s));
  s = sample(); s.profileAddress[2][0] = 'g'; seal(s); assert(!valid(s));
  s = sample(); s.profileAddress[2][0] = 0; seal(s); assert(!valid(s));
  s = sample(); s.profileAddress[0][0] = 'x'; seal(s); assert(!valid(s));
  s = sample(); s.profileProtocol[0] = ProtocolCount; seal(s); assert(!valid(s));
  s = sample(); s.profileProtocol[2] = 1; seal(s); assert(!valid(s));
  s = sample(); s.profileEpoch[2]--; seal(s); assert(!valid(s));
  s = sample(); s.protocolEpoch[0]--; seal(s); assert(!valid(s));
  s = sample(); s.protocolEpoch[1] = EarliestClockUtc - 1; seal(s); assert(!valid(s));
  s = sample(); s.profileEpoch[0] = s.successEpoch - 1; seal(s); assert(!valid(s));
  s = sample(); s.profileEpoch[0] = EarliestClockUtc - 1;
  std::strcpy(s.profileAddress[0], "11:22:33:44:55:66"); seal(s); assert(!valid(s));
  // Clock corrections can make another profile's recorded success later than
  // the latest transaction. Preserve valid absolute times; do not invent order.
  s = sample(); s.profileEpoch[0] = s.successEpoch + 10;
  std::strcpy(s.profileAddress[0], "11:22:33:44:55:66");
  s.protocolEpoch[1] = s.successEpoch + 10; seal(s); assert(valid(s));
  // An unsynchronized bound watch is legitimate; it has no fabricated success.
  s = sample(); std::strcpy(s.profileAddress[0], "11:22:33:44:55:66"); seal(s); assert(valid(s));
  s = sample(); std::strcpy(s.profileAddress[2], "a1:b2:c3:d4:e5:f6"); seal(s); assert(valid(s));
  std::puts("Malformed schema, epoch, quota, profile, protocol and address fields rejected; unset profiles retained");
}
int main() {
  quota(); corruption(); validation();
}
'''

class BtHistoryTest(unittest.TestCase):
    def test_snapshot_and_daily_quota(self):
        self.assertIsNotNone(shutil.which('g++'), 'g++ is required for BT history tests')
        with tempfile.TemporaryDirectory(prefix='casiosync-bt-history-') as tmp:
            source, binary = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
            source.write_text(DRIVER)
            subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
                            '-I', str(FIRMWARE.parent), str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

if __name__ == "__main__": unittest.main()
