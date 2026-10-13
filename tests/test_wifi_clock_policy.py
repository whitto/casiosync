#!/usr/bin/env python3
"""Run actual Wi-Fi wake decisions with monotonic time and SDK failures controlled."""
import re
import unittest
from support import FIRMWARE, MOCKS, balanced_block, extract_function, run_cpp

NETWORK_MOCKS=r'''
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
int clockMux=0;
uint64_t monoMs=1000;int64_t esp_timer_get_time(){return static_cast<int64_t>(monoMs*1000);}
uint32_t millis(){return static_cast<uint32_t>(monoMs);}
uint32_t clockNtpSyncCount=1,clockAge=0;bool clockNtpRejected=false;
uint32_t clockAgeSeconds(){return clockAge;}
std::atomic<uint32_t> ntpIntervalSec{3600};
bool wifiClockWakeActive=false;uint32_t wifiClockWakeSyncCount=0;
uint64_t wifiClockWakeStartedMs=0,wifiClockRetryAtMs=0;
uint32_t wifiClockRetryDelayMs=30000;
constexpr uint32_t WIFI_CLOCK_WAKE_TIMEOUT_MS=120000,WIFI_RETRY_MAX_MS=900000,WIFI_CLOCK_WAKE_LEAD_SEC=60;
constexpr int WIFI_OFF=0,WIFI_STA=1,WIFI_POWER_ALWAYS_ON=0,WIFI_POWER_SCHEDULED=1;
constexpr uint32_t WIFI_BOOT_ON_DURATION_MS=300000;
uint32_t bootMillis=0,wifiRecoveryStarted=0;
bool wifiBootAccessComplete=true,wifiRecoveryWindowActive=false;
bool ap_mode=false,filesystemAvailable=true,wifiConnectionPending=false;
bool wifiRadioEnabled=true,wifiPowerFault=false,wifiPowerShutdownPending=false;
int wifiPowerMode=WIFI_POWER_SCHEDULED;
bool access=false,schedule=false;
bool wifiAccessWindowOpen(){return access;}
bool shouldWifiBeOnForBtSchedule(){return schedule;}
struct WifiMock{int mode=WIFI_STA;bool setSleep(bool){return true;}int getMode(){return mode;}}WiFi;
struct SerialMock{void println(const char*){}}Serial;
int starts=0,stops=0;
void ntpstart(){++starts;WiFi.mode=WIFI_STA;}
bool ntpstop(){++stops;WiFi.mode=WIFI_OFF;wifiPowerShutdownPending=false;return true;}
'''

NETWORK_DRIVER=r'''
void inspect(){monoMs+=1001;updateWifiPowerManagement();}
int main(){
 // An idle trusted-clock device closes Wi-Fi outside user/BT/clock wakes.
 inspect();assert(!wifiRadioEnabled&&WiFi.mode==WIFI_OFF&&stops==1);
 access=true;inspect();assert(wifiRadioEnabled&&WiFi.mode==WIFI_STA&&starts==1);
 inspect();assert(starts==1);access=false;inspect();assert(!wifiRadioEnabled&&stops==2);
 schedule=true;inspect();assert(wifiRadioEnabled&&starts==2);schedule=false;
 // Initial access and newly supplied credentials retain finite access grace.
 wifiBootAccessComplete=false;bootMillis=millis();inspect();assert(wifiRadioEnabled);
 monoMs+=WIFI_BOOT_ON_DURATION_MS;inspect();assert(!wifiRadioEnabled&&wifiBootAccessComplete);
 wifiRecoveryWindowActive=true;wifiRecoveryStarted=millis();inspect();assert(wifiRadioEnabled);
 monoMs+=WIFI_BOOT_ON_DURATION_MS;inspect();assert(!wifiRadioEnabled&&!wifiRecoveryWindowActive);
 // Provisioning, unavailable storage and active association retain access.
 access=true;inspect();assert(wifiRadioEnabled);access=false;
 const int oldStops=stops;ap_mode=true;inspect();assert(wifiRadioEnabled&&stops==oldStops);
 ap_mode=false;filesystemAvailable=false;inspect();assert(wifiRadioEnabled&&stops==oldStops);
 filesystemAvailable=true;wifiConnectionPending=true;inspect();assert(wifiRadioEnabled&&stops==oldStops);
 wifiConnectionPending=false;inspect();assert(!wifiRadioEnabled);
 // Always-on overrides all scheduling and restores an intentionally off station.
 wifiPowerMode=WIFI_POWER_ALWAYS_ON;inspect();assert(wifiRadioEnabled);
 wifiPowerMode=WIFI_POWER_SCHEDULED;
 // Adaptive NTP wake starts one minute before the one-hour refresh deadline.
 clockAge=3539;assert(!wifiClockSyncWindowOpen());
 clockAge=3540;assert(wifiClockSyncWindowOpen()&&wifiClockWakeActive);
 const uint64_t begun=wifiClockWakeStartedMs;
 monoMs=begun+WIFI_CLOCK_WAKE_TIMEOUT_MS-1;assert(wifiClockSyncWindowOpen());
 ++monoMs;assert(!wifiClockSyncWindowOpen()&&!wifiClockWakeActive);
 assert(wifiClockRetryAtMs==monoMs+30000&&wifiClockRetryDelayMs==60000);
 const uint64_t retry=wifiClockRetryAtMs;
 monoMs=retry-1;assert(!wifiClockSyncWindowOpen());
 ++monoMs;assert(wifiClockSyncWindowOpen());
 // Only an accepted confirmed reply completes a wake; stale/rejected replies do not.
 ++clockNtpSyncCount;clockNtpRejected=true;assert(wifiClockSyncWindowOpen());
 clockNtpRejected=false;clockAge=0;assert(!wifiClockSyncWindowOpen());
 assert(!wifiClockWakeActive&&wifiClockRetryAtMs==0&&wifiClockRetryDelayMs==30000);
 // No valid NTP age starts bounded recovery. Repeated failures have capped backoff.
 clockAge=UINT32_MAX;
 for(int i=0;i<15;++i){
   monoMs=wifiClockRetryAtMs>monoMs?wifiClockRetryAtMs:monoMs;
   assert(wifiClockSyncWindowOpen());monoMs+=WIFI_CLOCK_WAKE_TIMEOUT_MS;
   assert(!wifiClockSyncWindowOpen());assert(wifiClockRetryDelayMs<=WIFI_RETRY_MAX_MS);
 }
 assert(wifiClockRetryDelayMs==WIFI_RETRY_MAX_MS);
 // The clock wake's 64-bit deadlines remain valid beyond millis rollover and years.
 monoMs=(1ULL<<32)+1000;wifiClockRetryAtMs=0;wifiClockWakeActive=false;
 assert(wifiClockSyncWindowOpen());monoMs+=WIFI_CLOCK_WAKE_TIMEOUT_MS;
 assert(!wifiClockSyncWindowOpen());
 monoMs=20ULL*365*86400*1000;wifiClockRetryAtMs=0;wifiClockWakeActive=false;
 assert(wifiClockSyncWindowOpen());++clockNtpSyncCount;clockAge=0;
 assert(!wifiClockSyncWindowOpen());
 std::puts("Actual Wi-Fi/clock policy: user and BT windows, startup/AP exceptions, confirmed-reply recovery, capped retries and years-long time passed");
}
'''

class WifiClockPolicyTest(unittest.TestCase):
    def test_actual_network_wakes_and_recovery_budget(self):
        source=FIRMWARE.read_text()
        functions='\n'.join(extract_function(source,n) for n in ('wifiClockSyncWindowOpen','updateWifiPowerManagement'))
        # Match ESP32 unsigned long width for its startup/association grace.
        functions=functions.replace('const unsigned long now','const uint32_t now').replace('static unsigned long lastCheck','static uint32_t lastCheck')
        run_cpp(MOCKS+NETWORK_MOCKS+functions+NETWORK_DRIVER)

    def test_actual_sntp_admission_commit_and_reacquisition(self):
        source=FIRMWARE.read_text()
        globals=source[source.index('uint64_t ntpLastMonoUs ='):source.index('uint64_t monotonicUptimeSeconds()')]
        constants='\n'.join(re.findall(r'^#define NTP_[^\n]*',source,re.M))+'\n'
        names=('clockAgeSeconds','clockEstimatedError','clockConfidence','clockTrusted',
               'ntpReplyPlausible','rejectNtpReply','admitNtpReply','recordAcceptedNtpReply','configureAdaptiveNtp')
        functions='\n'.join(extract_function(source,n) for n in names)
        strong=balanced_block(source,source.index('extern "C" void sntp_sync_time('))
        run_cpp(MOCKS+r'''
#include <sys/time.h>
#include <cmath>
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
int clockMux=0;
uint64_t monoUs=1000000;int64_t esp_timer_get_time(){return static_cast<int64_t>(monoUs);}
std::atomic<int> ntpsync{0};
uint32_t sdkInterval=0;void sntp_set_sync_interval(uint32_t n){sdkInterval=n;}
constexpr int SNTP_SYNC_STATUS_RESET=0,SNTP_SYNC_STATUS_COMPLETED=1;
int sdkStatus=SNTP_SYNC_STATUS_RESET;void sntp_set_sync_status(int n){sdkStatus=n;}
bool denyCommit=false;int commits=0;int64_t committedEpoch=0;
int fakeSetTime(const struct timeval* tv,void*){
 ++commits;if(denyCommit)return -1;
 committedEpoch=static_cast<int64_t>(tv->tv_sec)*1000000LL+tv->tv_usec;return 0;
}
#define settimeofday fakeSetTime
void configureAdaptiveNtp();
'''+globals+constants+functions+strong+r'''
void reply(int64_t seconds,int usec=0){timeval tv{static_cast<time_t>(seconds),usec};sntp_sync_time(&tv);}
int main(){
 const int64_t anchor=1791858600;
 assert(!clockTrusted());reply(anchor);assert(commits==0&&clockNtpCandidateReplyCount==1&&!clockTrusted());
 // Duplicates inside the minimum step cannot increase the acquisition count.
 for(int i=0;i<100;++i)reply(anchor);
 assert(commits==0&&clockNtpCandidateReplyCount==1);
 monoUs+=10000000;reply(anchor+10);assert(commits==0&&clockNtpCandidateReplyCount==2);
 monoUs+=20000000;reply(anchor+30,123000);
 assert(commits==1&&clockNtpSyncCount==1&&clockTrusted()&&sdkStatus==SNTP_SYNC_STATUS_COMPLETED);
 assert(ntpIntervalSec==3600&&sdkInterval==3600000);
 assert(committedEpoch==(anchor+30)*1000000LL+123000);
 // An in-range update remains accepted and derives drift from a five-minute span.
 monoUs+=600000000;reply(anchor+630,183000);
 assert(commits==2&&clockNtpSyncCount==2&&clockDriftSampleAvailable&&clockTrusted());
 assert(ntpIntervalSec<=3600&&ntpIntervalSec>=15);
 // A gross wall-clock correction is rejected BEFORE touching the SDK clock.
 monoUs+=15000000;reply(anchor+100000);
 assert(commits==2&&sdkStatus==SNTP_SYNC_STATUS_RESET&&!clockTrusted());
 assert(clockNtpCandidateReplyCount==1&&ntpIntervalSec==15);
 monoUs+=15000000;reply(anchor+100015);assert(commits==2&&clockNtpCandidateReplyCount==2);
 monoUs+=15000000;reply(anchor+100030);
 assert(commits==3&&clockNtpSyncCount==3&&clockNtpReacquisitionCount==1&&clockTrusted());
 assert(!clockDriftSampleAvailable&&clockDriftBoundPpm==CLOCK_INITIAL_PPM);
 assert(ntpIntervalSec==3600);
 // Invalid epochs/fractions restart acquisition without a commit.
 reply(0);assert(commits==3&&!clockTrusted()&&clockNtpCandidateReplyCount==0);
 reply(anchor,-1);assert(commits==3&&clockNtpCandidateReplyCount==0);
 reply(anchor,1000000);assert(commits==3&&clockNtpCandidateReplyCount==0);
 reply(4102444800LL);assert(commits==3&&clockNtpCandidateReplyCount==0);
 // Even three consistent replies do not restore trust if wall-clock commit fails.
 monoUs+=10000000;reply(anchor+100040);
 monoUs+=15000000;reply(anchor+100055);
 monoUs+=15000000;denyCommit=true;reply(anchor+100070);
 assert(commits==4&&!clockTrusted()&&clockNtpSyncCount==3&&sdkStatus==SNTP_SYNC_STATUS_RESET);
 assert(committedEpoch==(anchor+100030)*1000000LL);
 std::puts("Actual SNTP strong gate: three advancing replies, no duplicate promotion, rejected precommit, drift/reacquisition and commit failure passed");
}
''')

if __name__=='__main__':unittest.main()
