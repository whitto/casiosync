#!/usr/bin/env python3
"""Fault-inject durable per-watch choices and identity-safe reboot restoration."""
import unittest
from support import FIRMWARE, MOCKS, extract_function, run_cpp
from test_storage_policy import STORAGE_MOCKS

OPTIONS_MOCKS=r'''
#include "CasioWatchOptions.h"
constexpr const char* WATCH_OPTIONS_FILE="options",*WATCH_OPTIONS_TEMP_FILE="options.tmp";
bool filesystemAvailable=true;
CasioWatchFeatures::Desired btFeatureDesired[4];
char btFeatureBoundAddress[4][18]={};uint8_t btFeatureBoundProtocol[4]={};
const char* btFeatureStatus[4]={};
'''

OPTIONS_DRIVER=r'''
int main(){
 static_assert(sizeof(CasioWatchOptions::Snapshot)<=256,"bounded persistent options");
 loadWatchOptions();assert(writeOpens==0&&flash.empty());
 for(int i=0;i<4;++i)assert(!btFeatureDesired[i].enabled&&btFeatureBoundAddress[i][0]==0);
 btProfileAddress[0]="aa:bb:cc:dd:ee:ff";btProfileProtocol[0]=0;
 strlcpy(btFeatureBoundAddress[0],btProfileAddress[0].c_str(),18);
 auto &desired=btFeatureDesired[0];desired.enabled=true;desired.alarmsEnabled=true;
 desired.alarms[0]={true,12,34};desired.hourlyChime=1;
 desired.timerEnabled=true;desired.timerSeconds=3600;desired.basicMask=0x7f;
 desired.buttonTone=false;desired.language=4;desired.autoAdjustEnabled=true;desired.autoAdjustMinute=59;
 assert(saveWatchOptions()&&writeOpens==1&&renames==1);
 const std::string previous=flash.at(WATCH_OPTIONS_FILE);
 CasioWatchOptions::Snapshot saved{};std::memcpy(&saved,previous.data(),sizeof(saved));
 assert(CasioWatchOptions::valid(saved));
 // Every bit, including header/padding/trailer bits, is protected before decode.
 for(size_t byte=0;byte<sizeof(saved);++byte)for(unsigned bit=0;bit<8;++bit){
  auto damaged=saved;reinterpret_cast<uint8_t*>(&damaged)[byte]^=static_cast<uint8_t>(1U<<bit);
  assert(!CasioWatchOptions::valid(damaged));
 }
 auto invalid=saved;invalid.profiles[0].enabled=2;CasioWatchOptions::seal(invalid);assert(!CasioWatchOptions::valid(invalid));
 invalid=saved;invalid.profiles[0].timerSeconds=0;CasioWatchOptions::seal(invalid);assert(!CasioWatchOptions::valid(invalid));
 invalid=saved;invalid.profiles[0].autoAdjustMinute=60;CasioWatchOptions::seal(invalid);assert(!CasioWatchOptions::valid(invalid));
 // Actual startup loads restore the bound watch only and never write.
 btFeatureDesired[0]={};loadWatchOptions();assert(writeOpens==1&&btFeatureDesired[0].enabled);
 assert(btFeatureDesired[0].alarms[0].enabled&&btFeatureDesired[0].alarms[0].hour==12&&btFeatureDesired[0].alarms[0].minute==34);
 assert(btFeatureDesired[0].timerSeconds==3600&&btFeatureDesired[0].language==4&&btFeatureDesired[0].autoAdjustMinute==59);
 btProfileAddress[0]="AA:BB:CC:DD:EE:FF";loadWatchOptions();assert(btFeatureDesired[0].enabled);
 btProfileAddress[0]="11:22:33:44:55:66";loadWatchOptions();assert(!btFeatureDesired[0].enabled);
 btProfileAddress[0]="aa:bb:cc:dd:ee:ff";btProfileProtocol[0]=1;loadWatchOptions();assert(!btFeatureDesired[0].enabled);
 btProfileProtocol[0]=0;loadWatchOptions();assert(btFeatureDesired[0].enabled);
 // Open/short-write/readback/rename failures cannot replace the saved choices.
 btFeatureDesired[0].timerSeconds=60;
 for(int fault=0;fault<4;++fault){
  openOk=fault!=0;shortWrite=fault==1;corruptWrite=fault==2;renameOk=fault!=3;
  const int before=writeOpens;assert(!saveWatchOptions()&&writeOpens==before+1);
  assert(flash.at(WATCH_OPTIONS_FILE)==previous);
 }
 openOk=renameOk=true;shortWrite=corruptWrite=false;
 const int before=writeOpens;filesystemAvailable=false;assert(!saveWatchOptions()&&writeOpens==before);
 filesystemAvailable=true;flash[WATCH_OPTIONS_FILE][0]^=1;loadWatchOptions();
 assert(!btFeatureDesired[0].enabled&&writeOpens==before);
 for(size_t size=0;size<previous.size();++size){
  flash[WATCH_OPTIONS_FILE]=previous.substr(0,size);loadWatchOptions();
  assert(!btFeatureDesired[0].enabled&&writeOpens==before);
 }
 std::puts("Watch choices: CRC all-bit/truncation guards, confirmed identity, reboot restore, atomic write faults and no startup writes passed");
}
'''

class WatchOptionsStorageTest(unittest.TestCase):
    def test_actual_save_and_reboot_identity_with_faults(self):
        source=FIRMWARE.read_text()
        functions='\n'.join(extract_function(source,n) for n in ('loadWatchOptions','saveWatchOptions'))
        run_cpp(MOCKS+STORAGE_MOCKS+OPTIONS_MOCKS+functions+OPTIONS_DRIVER)

    def test_watch_options_write_is_explicit_and_not_a_sync_side_effect(self):
        source=FIRMWARE.read_text()
        for name in ('loop','attemptBluetoothSync','performGShockBX5600Sync','performCasioStandardTimeSync'):
            self.assertNotIn('saveWatchOptions',extract_function(source,name))
        self.assertNotIn('saveWatchOptions',extract_function(source,'loadWatchOptions'))
        handler=source[source.index('const auto previous=btFeatureDesired[profile]'):]
        for rollback in ('btFeatureDesired[profile]=previous','memcpy(btFeatureBoundAddress[profile],previousAddress',
                         'btFeatureBoundProtocol[profile]=previousProtocol'):
            self.assertIn(rollback,handler)
        self.assertLess(handler.index('if (!saveWatchOptions())'),handler.index('server.send(200')))

if __name__=='__main__':unittest.main()
