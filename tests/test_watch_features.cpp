#include "../firmware/CasioSync_V0_1/CasioWatchFeatures.h"
#include <array>
#include <cassert>
#include <cstring>
#include <iostream>

using namespace CasioWatchFeatures;

static void defaultsAndCapabilities() {
  Desired d;
  assert(!d.enabled && !d.alarmsEnabled && !d.timerEnabled && !d.autoAdjustEnabled);
  assert(d.basicMask == 0 && d.hourlyChime == -1 && validDesired(d));
  const auto bx = capabilities("CASIO GW-BX5600", 15);
  assert(bx.alarmCount == 5 && bx.basicMask == kAllBasic && bx.timer && bx.autoAdjust);
  const auto dw = capabilities("DW-B5600", 8);
  assert(dw.alarmCount == 5 && !(dw.basicMask & kAutoLight));
  assert(capabilities("unidentified watch", 18).alarmCount == 0);
  assert(capabilities("MTG-B3000", 9).alarmCount == 0);
  size_t featureCandidates = 0;
  for (const auto &entry : CasioModelCatalog::Models) {
    const auto caps = capabilities(entry.model, strlen(entry.model));
    if (entry.protocol == CasioModelCatalog::Protocol::Analogue) {
      assert(caps.alarmCount == 0 && caps.basicMask == 0 && !caps.timer);
    } else {
      assert(caps.alarmCount == 5 && caps.timer && caps.autoAdjust);
      assert((caps.basicMask & ~kAllBasic) == 0);
      assert(caps.timerMaxSeconds == 3600 || caps.timerMaxSeconds == 86400);
      ++featureCandidates;
    }
  }
  assert(featureCandidates == 119);
  d.autoAdjustMinute = 60; assert(!validDesired(d));
  d.autoAdjustMinute = 59; d.timerSeconds = 0; assert(!validDesired(d));
  d.timerSeconds = 86401; assert(!validDesired(d));
  d.timerSeconds = 86400; d.alarms[4].hour = 24; assert(!validDesired(d));
  d.alarms[4].hour = 23; d.alarms[4].minute = 60; assert(!validDesired(d));
  d.alarms[4].minute = 59; d.language = 6; assert(!validDesired(d));
  d.language = 5; d.basicMask = 0x80; assert(!validDesired(d));
}

static void capturedBasicAndKeep() {
  // Official GW-BX5600 0x13 read/write, btsnoop_hci-bx2.txt #975/#979.
  const uint8_t capture[] = {0x13,0x00,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
  std::array<uint8_t,17> out{};
  Desired d;
  assert(mergeBasic(capture,sizeof(capture),kAllBasic,d,out.data(),out.size()));
  assert(memcmp(capture,out.data(),sizeof(capture)) == 0);
  d.basicMask = kTimeFormat | kButtonTone | kAutoLight | kPowerSaving | kLightDuration | kDateFormat | kLanguage;
  d.timeFormat24 = true; d.buttonTone = false; d.autoLight = false;
  d.powerSaving = false; d.longLight = false; d.dateDayFirst = true; d.language = 4;
  assert(mergeBasic(capture,sizeof(capture),kAllBasic,d,out.data(),out.size()));
  const uint8_t expected[] = {0x13,0x17,0x00,0x00,0x01,0x04,0x00,0x00,0x00,0x00,0x00,0x00};
  assert(memcmp(out.data(),expected,sizeof(expected)) == 0);
  assert(basicMatches(out.data(),sizeof(capture),kAllBasic,d));
  out[8] = 0x20; // An unrelated font change must not invalidate matching settings.
  assert(basicMatches(out.data(),sizeof(capture),kAllBasic,d));
  out[1] ^= 0x01; assert(!basicMatches(out.data(),sizeof(capture),kAllBasic,d));
  out.fill(0xa5);
  assert(!mergeBasic(capture,sizeof(capture),kAllBasic & ~kAutoLight,d,out.data(),out.size()));
  for (uint8_t b : out) assert(b == 0xa5);
}

static void extendedBasicPreservation() {
  // Captured 17-byte extended layout, btsnoop_hci_DW-H5600-2.txt #38649.
  // H5600 itself is excluded from the supported catalog; this tests parsing
  // and preserving the upstream extended layout, not device compatibility.
  uint8_t packet[] = {0x13,0x00,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x24,0x00,0x00,0x06,0x00};
  const auto original = std::array<uint8_t,17>{0x13,0x00,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x24,0x00,0x00,0x06,0x00};
  Desired d; d.basicMask = kButtonTone; d.buttonTone = false;
  assert(mergeBasic(packet,sizeof(packet),kAllBasic,d,packet,sizeof(packet)));
  assert(packet[1] == 0x02 && packet[12] == 0x20);
  for (size_t i = 0; i < sizeof(packet); ++i) {
    if (i != 1 && i != 12) assert(packet[i] == original[i]);
  }
  assert(basicMatches(packet,sizeof(packet),kAllBasic,d));
}

static void capturedAutoAdjust() {
  // Actual BX 15-byte response, btsnoop_hci-bx2.txt #889.
  uint8_t packet[] = {0x11,0x0f,0x0f,0x0f,0x06,0x00,0x50,0x00,0x04,0x00,0x01,0x00,0x00,0x1e,0x03};
  const auto original = std::array<uint8_t,15>{0x11,0x0f,0x0f,0x0f,0x06,0x00,0x50,0x00,0x04,0x00,0x01,0x00,0x00,0x1e,0x03};
  Desired d; d.autoAdjustEnabled = true; d.autoAdjust = false; d.autoAdjustMinute = 59;
  assert(mergeAutoAdjust(packet,sizeof(packet),d,packet,sizeof(packet)));
  assert(packet[12] == 0x80 && packet[13] == 59 && autoAdjustMatches(packet,sizeof(packet),d));
  for (size_t i=0;i<sizeof(packet);++i) if(i!=12 && i!=13) assert(packet[i]==original[i]);
  packet[12] = 0x8f; // Preserve unknown lower flag bits in inverse enable byte.
  d.autoAdjust = true;
  assert(mergeAutoAdjust(packet,sizeof(packet),d,packet,sizeof(packet)));
  assert(packet[12] == 0x0f && autoAdjustMatches(packet,sizeof(packet),d));
  packet[13] = 58; assert(!autoAdjustMatches(packet,sizeof(packet),d));
}

static void capturedTimerAndShape() {
  // Actual BX countdown read, bx3_smart_sync_app.txt #1393.
  const uint8_t capture[] = {0x18,0x00,0x06,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
  std::array<uint8_t,17> out{};
  Desired d; d.timerEnabled = true; d.timerSeconds = 3661;
  assert(mergeTimer(capture,sizeof(capture),d,out.data(),out.size()));
  assert(out[0] == 0x18 && out[1] == 1 && out[2] == 1 && out[3] == 1);
  assert(timerMatches(out.data(),sizeof(capture),d));
  for (size_t i=4;i<sizeof(capture);++i) assert(out[i]==capture[i]);
  for (size_t size : {size_t(6),size_t(7),size_t(15)}) {
    uint8_t reply[17] = {0x18,0,1,0,0xa5,0x5a,0x9c,1,2,3,4,5,6,7,8,9,10};
    uint8_t before[17]; memcpy(before,reply,sizeof(reply));
    d.timerSeconds = 86400;
    assert(mergeTimer(reply,size,d,reply,sizeof(reply)));
    assert(reply[1]==24 && reply[2]==0 && reply[3]==0 && timerMatches(reply,size,d));
    for(size_t i=4;i<sizeof(reply);++i) assert(reply[i]==before[i]);
  }
}

static void alarmsAndReservedFields() {
  // Actual H5600 read shape #73/#74; source AlarmIO uses the same 0x15/16
  // four-byte records. The byte after flags is captured as zero, contrary to
  // one upstream encoder's hard-coded 0x40: merging must preserve it.
  uint8_t first[] = {0x15,0x40,0x00,0x06,0x2d};
  uint8_t secondary[] = {0x16,0x40,0x00,0x08,0x00,0x40,0x00,0x0c,0x00,0x00,0x00,0x09,0x00,0x00,0x00,0x09,0x19};
  Desired d; d.alarmsEnabled = true; d.hourlyChime = 1;
  for(size_t i=0;i<kAlarmCount;++i) {d.alarms[i].enabled=(i%2==0);d.alarms[i].hour=uint8_t(7+i);d.alarms[i].minute=uint8_t(10+i);}
  first[1] |= 0x13; // Preserve unknown flag bits.
  assert(mergeFirstAlarm(first,sizeof(first),d,first,sizeof(first)));
  assert(first[1] == 0xd3 && first[2] == 0 && first[3]==7 && first[4]==10 && firstAlarmMatches(first,sizeof(first),d));
  assert(mergeOtherAlarms(secondary,sizeof(secondary),5,d,secondary,sizeof(secondary)));
  assert(otherAlarmsMatch(secondary,sizeof(secondary),5,d));
  for(size_t i=1;i<kAlarmCount;++i) assert(secondary[2+(i-1)*4] == 0);
  secondary[3] ^= 1; assert(!otherAlarmsMatch(secondary,sizeof(secondary),5,d));
  // Keep alarm values when only the hourly chime is selected.
  d.alarmsEnabled=false; d.hourlyChime=0;
  const uint8_t oldHour=first[3],oldMinute=first[4],oldEnabled=first[1]&0x40;
  assert(mergeFirstAlarm(first,sizeof(first),d,first,sizeof(first)));
  assert(!(first[1]&0x80) && (first[1]&0x40)==oldEnabled && first[3]==oldHour && first[4]==oldMinute);
}

static void malformedPacketsAreNonDestructive() {
  Desired d; d.enabled=true; d.timerEnabled=true; d.basicMask=kTimeFormat;
  std::array<uint8_t,64> input{}; std::array<uint8_t,64> out;
  for(size_t length=0;length<input.size();++length) {
    input.fill(0); input[0]=0xff; out.fill(0xa5);
    assert(!mergeFirstAlarm(input.data(),length,d,out.data(),out.size()));
    assert(!mergeOtherAlarms(input.data(),length,5,d,out.data(),out.size()));
    assert(!mergeTimer(input.data(),length,d,out.data(),out.size()));
    assert(!mergeBasic(input.data(),length,kAllBasic,d,out.data(),out.size()));
    assert(!mergeAutoAdjust(input.data(),length,d,out.data(),out.size()));
    for(uint8_t b:out) assert(b==0xa5);
  }
  // Check every short/oversized length against each recognized header. A
  // valid zero-filled response may merge, but all other sizes must reject
  // without changing any byte of the caller's guarded output.
  for (uint8_t header : {kFirstAlarmHeader,kOtherAlarmsHeader,kTimerHeader,kBasicHeader,kAutoAdjustHeader}) {
    for (size_t length=0;length<input.size();++length) {
      input.fill(0); input[0]=header; out.fill(0xa5);
      bool result=false,expected=false;
      switch(header) {
        case kFirstAlarmHeader: result=mergeFirstAlarm(input.data(),length,d,out.data(),out.size());expected=(length==5);break;
        case kOtherAlarmsHeader:result=mergeOtherAlarms(input.data(),length,5,d,out.data(),out.size());expected=(length==17);break;
        case kTimerHeader:result=mergeTimer(input.data(),length,d,out.data(),out.size());expected=(length==6||length==7||length==15);break;
        case kBasicHeader:result=mergeBasic(input.data(),length,kAllBasic,d,out.data(),out.size());expected=(length==12||length==17);break;
        case kAutoAdjustHeader:result=mergeAutoAdjust(input.data(),length,d,out.data(),out.size());expected=(length==15);break;
      }
      assert(result==expected);
      if(!result) for(uint8_t b:out) assert(b==0xa5);
      else for(size_t i=length;i<out.size();++i) assert(out[i]==0xa5);
    }
  }
  uint8_t timer[6]={0x18,25,0,0,0,0}; out.fill(0xa5);
  assert(!mergeTimer(timer,sizeof(timer),d,out.data(),out.size()));
  timer[1]=24; timer[3]=1; assert(!mergeTimer(timer,sizeof(timer),d,out.data(),out.size()));
  timer[1]=0;timer[3]=60;assert(!mergeTimer(timer,sizeof(timer),d,out.data(),out.size()));
  timer[3]=0;assert(!mergeTimer(timer,sizeof(timer),d,out.data(),5));
  uint8_t basic[12]={0x13}; assert(!mergeBasic(basic,sizeof(basic),kAllBasic,d,nullptr,17));
  assert(!mergeBasic(nullptr,sizeof(basic),kAllBasic,d,out.data(),out.size()));
  uint8_t automatic[15]={0x11};automatic[13]=60;
  assert(!mergeAutoAdjust(automatic,sizeof(automatic),d,out.data(),out.size()));
  for(uint8_t b:out) assert(b==0xa5);
}

int main() {
  defaultsAndCapabilities(); capturedBasicAndKeep(); extendedBasicPreservation();
  capturedAutoAdjust(); capturedTimerAndShape(); alarmsAndReservedFields();
  malformedPacketsAreNonDestructive();
  std::cout << "Watch features: defaults, captured layouts, selective readback, reserved bytes, aliasing and malformed packet checks passed\n";
}
