#!/usr/bin/env python3
"""Exercise real civil-time conversions and automatic-window state decisions.

These host fixtures run production functions, with BLE transport and wall time
under explicit control. They prove schedule admission, not watch advertising.
"""
import re
import unittest
from support import FIRMWARE, MOCKS, balanced_block, extract_function, run_cpp

TIME_MOCKS = r'''
#include "CasioWifiAccessWindow.h"
String btTimezoneName="Australia/Brisbane";
int btTimeOffsetMinutes=0;
bool wifiAccessEnabled=true;
int wifiAccessStart=1080, wifiAccessEnd=1200;
String wifiAccessTimezone="Australia/Brisbane";
time_t fakeEpoch=0;
time_t fakeTime(time_t* out) { if(out) *out=fakeEpoch; return fakeEpoch; }
#define time fakeTime
time_t utc(int y,int m,int d,int h=0,int minute=0,int second=0) {
  struct tm t{}; t.tm_year=y-1900;t.tm_mon=m-1;t.tm_mday=d;
  t.tm_hour=h;t.tm_min=minute;t.tm_sec=second; return timegm(&t);
}
'''

TIME_DRIVER = r'''
int main() {
  struct tm local{};
  fakeEpoch=utc(2026,10,13,2,30);
  bluetoothLocalTime(fakeEpoch,local);
  assert(local.tm_hour==12 && local.tm_min==30 && local.tm_mday==13);
  btTimeOffsetMinutes=30; bluetoothLocalTime(fakeEpoch,local);
  assert(local.tm_hour==13 && local.tm_min==0);
  // Access windows have an independent timezone and do not inherit BT offsets.
  fakeEpoch=utc(2026,10,13,7,59,59); assert(!wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,8); assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,9,59,59); assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,10); assert(!wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,14,8); assert(wifiAccessWindowOpen());
  btTimeOffsetMinutes=-720; assert(wifiAccessWindowOpen());
  wifiAccessStart=1380;wifiAccessEnd=60;
  fakeEpoch=utc(2026,10,13,12,59,59); assert(!wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,13); assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,14,59,59); assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,13,15); assert(!wifiAccessWindowOpen());
  wifiAccessEnabled=false;assert(!wifiAccessWindowOpen());wifiAccessEnabled=true;
  fakeEpoch=0;assert(!wifiAccessWindowOpen());
  // Compare all advertised zones with the native POSIX rules through one year.
  const char* zones[]={"Australia/Brisbane","Australia/Sydney","Asia/Tokyo",
    "Asia/Shanghai","Europe/London","America/New_York","America/Los_Angeles","UTC"};
  btTimeOffsetMinutes=0;wifiAccessStart=90;wifiAccessEnd=210;
  for(const char* zone:zones) {
    btTimezoneName=wifiAccessTimezone=zone;
    setenv("TZ",posixTzFor(btTimezoneName).c_str(),1);tzset();
    const std::string unchanged=std::getenv("TZ");
    for(fakeEpoch=utc(2026,1,1);fakeEpoch<utc(2027,1,1);fakeEpoch+=17*60) {
      struct tm expected{};localtime_r(&fakeEpoch,&expected);bluetoothLocalTime(fakeEpoch,local);
      assert(local.tm_year==expected.tm_year && local.tm_yday==expected.tm_yday);
      assert(local.tm_hour==expected.tm_hour && local.tm_min==expected.tm_min);
      assert(local.tm_sec==expected.tm_sec && local.tm_isdst==expected.tm_isdst);
      assert(wifiAccessWindowOpen()==CasioWifiAccessWindow::containsMinute(expected.tm_hour*60+expected.tm_min,90,210));
      assert(std::getenv("TZ")==unchanged);
    }
  }
  wifiAccessTimezone="Australia/Sydney";wifiAccessStart=120;wifiAccessEnd=180;
  fakeEpoch=utc(2026,10,3,15,59,59);assert(!wifiAccessWindowOpen());
  fakeEpoch=utc(2026,10,3,16);assert(!wifiAccessWindowOpen());
  fakeEpoch=utc(2026,4,4,15,30);assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,4,4,16,30);assert(wifiAccessWindowOpen());
  fakeEpoch=utc(2026,4,4,17);assert(!wifiAccessWindowOpen());
  std::puts("Actual BT/access timezone helpers: Brisbane, offsets, recurring/overnight access and all-zone DST passed");
}
'''

SCHEDULE_MOCKS = r'''
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
constexpr int BT_SYNC_SLOT_COUNT=4,BT_WATCH_PROFILE_COUNT=4,BT_PROTOCOL_COUNT=3;
constexpr int BT_PROTOCOL_BX5600_MIP=0,BT_PROTOCOL_STANDARD=1,BT_PROTOCOL_ANALOGUE=2;
constexpr int BT_PREPARE_MINUTES=5,BT_WINDOW_AFTER_MINUTES=5,BT_MANUAL_WINDOW_MINUTES=7;
int btSyncTimes[4]={30,390,750,1110};
bool btSyncEnabled[4]={false,false,true,true};
uint8_t btSyncProfile[4]={0,0,0,0},btSyncProtocol[4]={0,0,0,0};
int btSlotAttemptYear[4]={-1,-1,-1,-1},btSlotAttemptYday[4]={-1,-1,-1,-1};
String btProfileAddress[4],btProfileName[4]; uint8_t btProfileProtocol[4]={};
uint8_t btManualProtocol=0,btActiveProtocol=0,btManualProfile=0,btActiveProfile=0;
bool btBleInitialized=true,btBleBusy=false,btWindowActive=false;
bool btPairModeActive=false,btPersistentWaitActive=false,btAlwaysWaitEnabled=false;
bool btPairRequested=false,btManualSyncRequested=false,btIdlePowerSaveEnabled=false;
bool btShutdownRecoveryActive=false,btControllerStarted=true;
std::atomic<bool> btShutdownRequested{false};
int btSyncActiveSlot=-1; uint32_t btWindowEndMillis=0;
String btLastWatchAddress,btLastWatchName,btLastSyncStatus;
uint8_t btLastWatchAddressType=0xff,btDiscoveryProtocol=0;
char btExpectedProfileAddress[18]={};int btDiscoveryMux=0;
const char* btPhase="Idle";
uint32_t tick=100;uint32_t millis(){return tick;}
struct SerialMock{void println(const char*){}template<class... T>void printf(const char*,T...){}}Serial;
constexpr int WL_CONNECTED=3;
struct WifiMock{int status(){return WL_CONNECTED;}}WiFi;
int ntpRestarts=0;void sntp_restart(){++ntpRestarts;}
bool validBtProtocol(int p){return p>=0&&p<3;}
const char* btProtocolName(int){return "fixture protocol";}
void clearBtDiscovery(){}
bool consumeBtDiscovery(String&,String&,uint8_t&){return false;}
void setBluetoothPhase(const char* p){btPhase=p;}
bool bleOperationCancelled(){return btShutdownRequested.load();}
void recoverBluetoothControllerShutdown(){btShutdownRequested=false;btControllerStarted=false;btBleInitialized=false;}
bool trustedClock=true;bool clockTrusted(){return trustedClock;}
int initialized=0,idleShutdowns=0;
void initBluetoothSync(){++initialized;btBleInitialized=true;}
bool serviceBtShutdownProgress(){return true;}
bool serviceBtClientQuarantine(){return true;}
bool btClientQuiescent(){return true;}
void disconnectGShock(){btBleBusy=false;}
bool bluetoothMemoryAvailable(bool=false){return true;}
void resetBluetoothDayIfNeeded(){}
bool shutdownIdleBluetooth(){++idleShutdowns;btBleInitialized=false;return true;}
bool attemptBluetoothSync(){return true;}
struct ScanMock{bool scanning=false;bool isScanning(){return scanning;}}scan;
ScanMock* btScan=&scan;
struct ScanControlMock{
 bool start(){scan.scanning=true;return true;}
 bool stop(){scan.scanning=false;return true;}
 bool quiescent(){return !scan.scanning;}
}btScanControl;
void stopBluetoothWindow();void startBluetoothWindow(int,bool=false);
void bind(int profile=0,int protocol=0){btProfileAddress[profile]="aa:bb:cc:dd:ee:ff";btProfileProtocol[profile]=protocol;}
'''

SCHEDULE_DRIVER = r'''
int main(){
  fakeEpoch=utc(2026,10,13,2,19,59);assert(!shouldWifiBeOnForBtSchedule());
  fakeEpoch=utc(2026,10,13,2,20);assert(shouldWifiBeOnForBtSchedule());
  fakeEpoch=utc(2026,10,13,2,35,59);assert(shouldWifiBeOnForBtSchedule());
  fakeEpoch=utc(2026,10,13,2,36);assert(!shouldWifiBeOnForBtSchedule());
  trustedClock=false;fakeEpoch=utc(2026,10,13,2,20);assert(!shouldWifiBeOnForBtSchedule());trustedClock=true;
  fakeEpoch=utc(2026,10,13,2,24,59);bind();
  assert(!bluetoothControllerNeeded());serviceBluetoothSync();assert(!btWindowActive);
  fakeEpoch=utc(2026,10,13,2,25);assert(bluetoothControllerNeeded());
  serviceBluetoothSync();assert(btWindowActive&&btSyncActiveSlot==2);
  assert(btActiveProfile==0&&btActiveProtocol==0&&!btPersistentWaitActive);
  assert(btSlotAttemptYear[2]==2026&&btSlotAttemptYday[2]==285);
  assert(btWindowEndMillis==tick+11*60*1000);
  const int firstNtp=ntpRestarts;
  serviceBluetoothSync();assert(ntpRestarts==firstNtp);
  tick=btWindowEndMillis;fakeEpoch=utc(2026,10,13,2,36);
  serviceBluetoothSync();assert(!btWindowActive);
  fakeEpoch=utc(2026,10,13,8,25);serviceBluetoothSync();assert(btWindowActive&&btSyncActiveSlot==3);
  stopBluetoothWindow();fakeEpoch=utc(2026,10,14,2,25);
  serviceBluetoothSync();assert(btWindowActive&&btSyncActiveSlot==2&&btSlotAttemptYday[2]==286);
  // A rejected unpaired/protocol-mismatched opening remains eligible today.
  stopBluetoothWindow();resetBluetoothSlotAttempt(2);btProfileAddress[0]="";
  serviceBluetoothSync();assert(!btWindowActive&&btSlotAttemptYear[2]==-1);
  bind(0,1);serviceBluetoothSync();assert(!btWindowActive&&btSlotAttemptYear[2]==-1);
  bind();serviceBluetoothSync();assert(btWindowActive&&btSyncActiveSlot==2);
  // An invalid automatic slot cannot interrupt a different valid passive watch.
  stopBluetoothWindow();resetBluetoothSlotAttempt(2);
  bind(1,1);btManualProfile=1;btManualProtocol=1;btAlwaysWaitEnabled=true;
  btProfileAddress[0]="";startBluetoothWindow(-1,true);
  const uint32_t passiveEnd=btWindowEndMillis;
  serviceBluetoothSync();assert(btWindowActive&&btPersistentWaitActive&&btActiveProfile==1);
  assert(btWindowEndMillis==passiveEnd&&btSlotAttemptYear[2]==-1);
  // Once pairing is available, automatic admission preempts passive listening.
  bind();serviceBluetoothSync();assert(btWindowActive&&!btPersistentWaitActive&&btSyncActiveSlot==2);
  // Slot edits rearm one slot only. Explicit manual requests stay active.
  stopBluetoothWindow();startBluetoothWindow(-1);resetBluetoothSlotAttempt(2);
  assert(btWindowActive&&btSyncActiveSlot==-1&&!btPersistentWaitActive);
  stopBluetoothWindow();btAlwaysWaitEnabled=false;btManualProfile=0;btManualProtocol=0;
  // Same window calculation uses watch civil time, including separate offset.
  btTimezoneName="UTC";btTimeOffsetMinutes=600;resetBluetoothSlotAttempt(2);
  serviceBluetoothSync();assert(btWindowActive&&btSyncActiveSlot==2);
  stopBluetoothWindow();btTimeOffsetMinutes=630;resetBluetoothSlotAttempt(2);
  serviceBluetoothSync();assert(!btWindowActive);
  // Preparation around midnight belongs to the scheduled target's date.
  btSyncTimes[0]=2;struct tm local{};local.tm_year=126;local.tm_yday=364;local.tm_hour=23;local.tm_min=59;
  int year,day;btSlotOccurrenceDate(0,local,year,day);assert(year==2027&&day==0);
  btSyncTimes[0]=1438;local.tm_year=127;local.tm_yday=0;local.tm_hour=0;local.tm_min=1;
  btSlotOccurrenceDate(0,local,year,day);assert(year==2026&&day==364);
  // The monotonic listening deadline survives 32-bit millis rollover.
  btTimezoneName="Australia/Brisbane";btTimeOffsetMinutes=0;
  fakeEpoch=utc(2026,10,15,2,25);tick=UINT32_MAX-100;
  resetBluetoothSlotAttempt(2);serviceBluetoothSync();assert(btWindowActive);
  tick+=11*60*1000-1;serviceBluetoothSync();assert(btWindowActive);
  ++tick;serviceBluetoothSync();assert(!btWindowActive);
  std::puts("Actual automatic windows: Brisbane 12:30/18:30, recurring dates, invalid binding retry, passive preservation, offset and rollover passed");
}
'''

class BluetoothScheduleTest(unittest.TestCase):
    def time_functions(self,source):
        names=('btWeekday','btNthSunday','btLastSunday','btDayOfYear','btDstAtUtc',
               'btBaseOffsetSeconds','bluetoothLocalTime','posixTzFor','wifiAccessWindowOpen')
        return '\n'.join(extract_function(source,n) for n in names)

    def test_actual_timezones_offsets_and_independent_access(self):
        source=FIRMWARE.read_text()
        run_cpp(MOCKS+TIME_MOCKS+self.time_functions(source)+TIME_DRIVER,timeout=45)

    def test_actual_automatic_window_state(self):
        source=FIRMWARE.read_text()
        time_functions=self.time_functions(source).replace('static String posixTzFor','String posixTzFor')
        # Exclude unused access helpers from this state-only translation unit.
        time_functions='\n'.join(extract_function(source,n) for n in
            ('btWeekday','btNthSunday','btLastSunday','btDayOfYear','btDstAtUtc','btBaseOffsetSeconds','bluetoothLocalTime'))
        functions='\n'.join(extract_function(source,n) for n in
            ('btMinutesOfDay','btMinuteInBluetoothWindow','btSlotOccurrenceDate','bluetoothProfileBindingReady',
             'startBluetoothWindow','stopBluetoothWindow','resetBluetoothSlotAttempt','bluetoothControllerNeeded','shouldWifiBeOnForBtSchedule','serviceBluetoothSync'))
        # long is 32-bit on ESP32; preserve that target width in host rollover tests.
        functions=re.sub(r'\(long\)\s*\(', '(int32_t)(',functions)
        run_cpp(MOCKS+TIME_MOCKS+SCHEDULE_MOCKS+time_functions+functions+SCHEDULE_DRIVER)

    def test_saved_time_changes_rearm_only_after_durable_commit(self):
        source=FIRMWARE.read_text()
        commit=balanced_block(source,source.index('const auto commitConfigWithBtTime ='))+';'
        mock=MOCKS.replace('bool reserve(size_t n) { s.reserve(n); return true; }',
                           'bool reserve(size_t n) { ++reserveCalls; if(denyReserve || reserveCalls==denyReserveAt)return false; s.reserve(n); return true; }')
        mock=mock.replace('class String {',
                          'bool denyReserve=false; int reserveCalls=0,denyReserveAt=0;\nclass String {',1)
        run_cpp(mock+r'''
constexpr int BT_SYNC_SLOT_COUNT=4;
String btTimezoneName="Australia/Brisbane";int btTimeOffsetMinutes=0;
String timezone_name="UTC";
char ssid[33]="old-network",passwd[65]="old-password";
int wifiPowerMode=0;bool btAlwaysWaitEnabled=false,wifiCredentialsReconnectPending=false;
int timezoneApplied=0;void applyTimezone(){++timezoneApplied;}
bool saveOk=false;int writes=0,rearms=0,failures=0;
unsigned rearmedSlots=0;
bool writeConfigNow(){++writes;return saveOk;}
bool configSaveFailed(const char*){++failures;return false;}
void resetBluetoothSlotAttempt(int slot){assert(slot>=0&&slot<4);++rearms;rearmedSlots|=1U<<slot;}
void assertOriginal(){
 assert(btTimezoneName=="Australia/Brisbane"&&btTimeOffsetMinutes==0);
 assert(timezone_name=="UTC"&&std::strcmp(ssid,"old-network")==0&&std::strcmp(passwd,"old-password")==0);
 assert(wifiPowerMode==0&&!btAlwaysWaitEnabled&&!wifiCredentialsReconnectPending&&timezoneApplied==0);
}
int main(){
 bool btTimeSettingsChanged=true;
 char previousBtZone[32]="Australia/Brisbane";
 const int previousBtOffset=0,requestedBtOffset=30;
 const char* nextBtZone="Asia/Tokyo";
 char previousDisplayZone[32]="UTC";
 const char* nextDisplayZone="Europe/London";
 char previousSsid[33]="old-network",previousPassword[65]="old-password";
 const int previousPowerMode=0,requestedPowerMode=1;
 const bool previousAlwaysWait=false,requestedAlwaysWait=true;
 const bool ssidRequested=true,passwordRequested=true;
 String requestedSsid="new-network",requestedPassword="new-password";
 bool wifiChanged=true;
'''+commit+r'''
 // A grouped save failure rolls back credentials, display/BT time, power and
 // listen choices together, and never applies/rearms/reconnects unsaved data.
 assert(!commitConfigWithBtTime());
 assertOriginal();assert(writes==1&&rearms==0&&rearmedSlots==0);
 denyReserve=true;saveOk=true;assert(!commitConfigWithBtTime());
 assertOriginal();assert(writes==1&&rearms==0&&failures==1);
 // Failure reserving the second String is equally atomic.
 denyReserve=false;reserveCalls=0;denyReserveAt=2;
 assert(!commitConfigWithBtTime());assertOriginal();
 assert(writes==1&&rearms==0&&failures==2);
 denyReserveAt=0;assert(commitConfigWithBtTime());
 assert(btTimezoneName=="Asia/Tokyo"&&btTimeOffsetMinutes==30);
 assert(timezone_name=="Europe/London"&&std::strcmp(ssid,"new-network")==0&&std::strcmp(passwd,"new-password")==0);
 assert(wifiPowerMode==1&&btAlwaysWaitEnabled&&wifiCredentialsReconnectPending&&timezoneApplied==1);
 assert(writes==2&&rearms==4&&rearmedSlots==15);
 // Retaining a password and unchanged BT/display time must not trigger BT
 // rearming or display-time application on another explicit settings save.
 btTimeSettingsChanged=false;timezone_name=previousDisplayZone;nextDisplayZone=previousDisplayZone;wifiChanged=false;
 requestedPassword="";std::strcpy(passwd,"old-password");wifiCredentialsReconnectPending=false;
 assert(commitConfigWithBtTime());
 assert(std::strcmp(passwd,"old-password")==0&&btTimezoneName=="Asia/Tokyo"&&btTimeOffsetMinutes==30);
 assert(writes==3&&rearms==4&&timezoneApplied==1&&!wifiCredentialsReconnectPending);
 std::puts("Actual grouped settings commit: credential/display/BT/power rollback, both allocation failures, durable four-slot rearm and unchanged-setting preservation passed");
}
''')

if __name__=='__main__':unittest.main()
