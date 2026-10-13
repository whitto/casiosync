#!/usr/bin/env python3
"""Fault-check production fixed-memory history, LED, config and access helpers."""
import unittest
from support import run_cpp

class RuntimeHelpersTest(unittest.TestCase):
    def test_led_blink_rollover_success_age_and_failure(self):
        run_cpp(r'''
#include "BtSyncLed.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
int main() {
  using namespace BtSyncLed;
  uint32_t phase=0; bool level=false, active=false;
  const int64_t success=1791453600;
  assert(!successEligible(0,success,true));
  assert(!successEligible(success-1,success,true));
  assert(successEligible(success,success,true));
  assert(successEligible(success+86399,success,true));
  assert(!successEligible(success+86400,success,true));
  assert(!successEligible(success+1,success,false));
  assert(!successEligible(success,0,true));
  assert(!output(100,false,true,true,phase,level,active));
  assert(output(100,true,true,false,phase,level,active));
  assert(output(349,true,true,false,phase,level,active));
  assert(!output(350,true,true,false,phase,level,active));
  assert(output(600,true,true,false,phase,level,active));
  assert(!output(1350,true,true,false,phase,level,active));
  assert(output(1350,true,false,true,phase,level,active));
  assert(!output(1351,true,false,false,phase,level,active));
  assert(!active);
  phase=0; level=active=false;
  assert(output(UINT32_MAX-100,true,true,false,phase,level,active));
  assert(!output(149,true,true,false,phase,level,active));
  assert(output(399,true,true,false,phase,level,active));
  assert(!output(400,false,false,true,phase,level,active));
  std::puts("LED: BT activity only, 24-hour UTC age, failure clears, off toggle and rollover passed");
}
''')

    def test_recent_attempts_are_fixed_ram_and_identity_isolated(self):
        run_cpp(r'''
#include "BtRecentSyncs.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
#include <type_traits>
int main() {
  static_assert(sizeof(BtRecentSyncs::Store)<=256,"bounded history RAM");
  static_assert(std::is_trivially_destructible<BtRecentSyncs::Store>::value,"no heap members");
  BtRecentSyncs::Store history;
  const char *watch="aa:bb:cc:dd:ee:ff", *other="11:22:33:44:55:66";
  assert(history.count(0)==0 && !history.latest(0,0));
  assert(!history.bind(4,watch,0));
  assert(history.bind(0,watch,0));
  for(uint32_t i=0;i<1000000;++i) {
    assert(history.record(0,watch,0,1704110400+i,i%2==0));
    assert(history.count(0)==(i<4?i+1:4));
    assert(history.latest(0,0)->utcEpoch==1704110400+i);
  }
  for(size_t i=0;i<4;++i) {
    const auto* entry=history.latest(0,i);
    assert(entry && entry->utcEpoch==1704110400+999999-i);
    assert(entry->successful==((999999-i)%2==0));
  }
  assert(!history.latest(0,4) && !history.latest(4,0));
  assert(history.bind(0,"AA:BB:CC:DD:EE:FF",0) && history.count(0)==4);
  assert(history.bind(1,other,2) && history.record(1,other,2,1704110500,true));
  assert(!history.record(0,other,0,1704110600,false));
  assert(history.count(0)==4 && history.count(1)==1);
  assert(history.bind(0,other,0) && history.count(0)==0);
  assert(history.record(0,other,0,0,false) && history.latest(0,0)->utcEpoch==0);
  assert(history.bind(0,other,1) && history.count(0)==0);
  assert(history.record(0,other,1,42,false) && history.latest(0,0)->utcEpoch==0);
  assert(!history.record(0,other,1,1704110700,false,true));
  assert(history.record(0,other,1,1704110700,true,true));
  for(const char* bad:{"", "a", "aa:bb", "aa:bb:cc:dd:ee:f", "aa:bb:cc:dd:ee:ffx", "gg:bb:cc:dd:ee:ff"})
    assert(!history.bind(0,bad,0));
  assert(!history.bind(0,other,3));
  BtRecentSyncs::Store rebooted; assert(rebooted.count(0)==0 && rebooted.count(1)==0);
  std::printf("Four-entry RAM history uses %zu bytes; million inserts, outcomes and identity isolation passed\n",sizeof(history));
}
''')

    def test_access_minutes_repeat_and_cross_midnight(self):
        run_cpp(r'''
#include "CasioWifiAccessWindow.h"
#include <cassert>
#include <cstdio>
int main() {
  using namespace CasioWifiAccessWindow;
  for(int minute=0;minute<1440;++minute) {
    assert(containsMinute(minute,1080,1200)==(minute>=1080 && minute<1200));
    assert(containsMinute(minute,1380,60)==(minute>=1380 || minute<60));
  }
  assert(!containsMinute(1080,1080,1080));
  assert(!containsMinute(-1,0,60) && !containsMinute(1440,0,60));
  assert(!containsMinute(0,-1,60) && !containsMinute(0,0,1440));
  std::puts("Wi-Fi access: exact daily edges, overnight windows and invalid inputs passed");
}
''')

    def test_config_integrity_foreign_record_rejection_and_bounds(self):
        run_cpp(r'''
#include "CasioConfigWriter.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
int main() {
  static_assert(CasioConfigFormat::FIELD_COUNT>=50 && CasioConfigFormat::FIELD_COUNT<=256,"bounded project schema");
  assert(std::strcmp(CasioConfigFormat::MAGIC,"CASIOSYNC_CONFIG_V1_CHECKSUMMED_SETTINGS")==0);
  char bytes[2048]; CasioConfigWriter writer(bytes,sizeof(bytes));
  assert(writer.line(CasioConfigFormat::MAGIC));
  for(size_t i=0;i<CasioConfigFormat::FIELD_COUNT;++i) assert(writer.number(static_cast<int>(i)));
  assert(writer.seal(CasioConfigFormat::FIELD_COUNT));
  const std::string original(bytes,writer.size());
  CasioConfigRecord record;
  assert(record.parse(bytes,writer.size()) && record.versioned() && record.count()==CasioConfigFormat::FIELD_COUNT);
  for(size_t i=0;i<CasioConfigFormat::FIELD_COUNT;++i) assert(record.number(i,-1)==static_cast<int>(i));
  record.restoreVersionedNewlines(); assert(std::string(bytes,writer.size())==original);
  for(size_t byte=0;byte<original.size();++byte) for(unsigned bit=0;bit<8;++bit) {
    std::vector<char> damaged(original.begin(),original.end()); damaged.push_back(0);
    damaged[byte]^=static_cast<char>(1U<<bit);
    assert(!record.parse(damaged.data(),original.size()));
  }
  for(size_t size=0;size<original.size();++size) {
    std::vector<char> cut(original.begin(),original.begin()+size); cut.push_back(0);
    assert(!record.parse(cut.data(),size));
  }
  for(const char* legacy:{"ssid\npassword\nAustralia/Brisbane\n", "RADIOCLOCK_CONFIG_V1_CHECKSUMMED_SETTINGS\n0\n"}) {
    std::string copy=legacy; copy.push_back(0);
    assert(!record.parse(copy.data(),copy.size()-1));
  }
  struct Guard { char before[4]; char body[8]; char after[4]; } guard={"abc",{},"xyz"};
  CasioConfigWriter tiny(guard.body,sizeof(guard.body));
  assert(tiny.line("123456")); assert(!tiny.line("x") && !tiny.seal(1));
  assert(std::strcmp(guard.before,"abc")==0 && std::strcmp(guard.after,"xyz")==0);
  CasioConfigWriter null(nullptr,0); assert(!null.line("x"));
  CasioConfigWriter bad(bytes,sizeof(bytes)); assert(!bad.line("line\nbreak"));
  int32_t number=17; uint32_t uns=17;
  assert(CasioConfigRecord::signedInteger("-2147483648",INT32_MIN,INT32_MAX,number) && number==INT32_MIN);
  assert(CasioConfigRecord::signedInteger("2147483647",INT32_MIN,INT32_MAX,number) && number==INT32_MAX);
  assert(!CasioConfigRecord::signedInteger("2147483648",INT32_MIN,INT32_MAX,number));
  assert(!CasioConfigRecord::signedInteger("-2147483649",INT32_MIN,INT32_MAX,number));
  assert(!CasioConfigRecord::signedInteger("1junk",-10,10,number));
  assert(CasioConfigRecord::unsignedInteger("4294967295",uns) && uns==UINT32_MAX);
  assert(!CasioConfigRecord::unsignedInteger("4294967296",uns));
  std::puts("Config: project-isolated schema, every bit/truncation, fixed buffer guards and numeric limits passed");
}
''')

if __name__ == '__main__': unittest.main()
