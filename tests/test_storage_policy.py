#!/usr/bin/env python3
"""Fault-inject production daily snapshot writes and audit runtime persistence."""
import re
import unittest
from support import FIRMWARE, MOCKS, extract_function, run_cpp

STORAGE_MOCKS=r'''
#include "BtSyncHistory.h"
#include <map>
#include <vector>
constexpr int BT_PROTOCOL_COUNT=3,BT_WATCH_PROFILE_COUNT=4;
constexpr const char *BT_HISTORY_FILE="snapshot",*BT_HISTORY_TEMP_FILE="snapshot.tmp";
bool btHistoryPersistEnabled=true;
uint32_t btHistoryGeneration=0,btHistorySavedEpoch=0,btHistorySnapshotGeneration=0;
int64_t btHistorySavedDay=-1,btHistoryAttemptDay=-1;
String btHistorySaveStatus;
uint8_t btActiveProfile=0,btActiveProtocol=0;
uint32_t btConnectionAttempts=3,btWriteAcknowledgements=4;
std::atomic<uint32_t> btNotifications{5},btResponseErrors{1};
uint32_t btProtocolLastSyncEpoch[3]={},btProfileLastSyncEpoch[4]={};
uint8_t btProfileLastSyncProtocol[4]={},btProfileProtocol[4]={};
String btProfileAddress[4],btProfileLastSyncAddress[4];
struct SerialMock{template<class... T>void printf(const char*,T...){}}Serial;
std::map<std::string,std::string> flash;
bool openOk=true,renameOk=true,shortWrite=false,corruptWrite=false;
int writeOpens=0,renames=0;
struct File{
 std::string* bytes=nullptr;size_t pos=0;
 explicit operator bool()const{return bytes;}
 size_t size()const{return bytes?bytes->size():0;}
 size_t read(uint8_t* out,size_t count){
  count=std::min(count,size()-std::min(pos,size()));
  if(count)std::memcpy(out,bytes->data()+pos,count);
  pos+=count;return count;
 }
 size_t write(const uint8_t* input,size_t count){
  if(shortWrite)count/=2;
  bytes->append(reinterpret_cast<const char*>(input),count);
  if(corruptWrite&&!bytes->empty())(*bytes)[0]^=1;
  return count;
 }
 void flush(){}void close(){}
};
struct LittleFsMock{
 File open(const char* name,const char* mode){
  if(*mode=='w'){++writeOpens;if(!openOk)return {};flash[name]="";return {&flash[name]};}
  auto it=flash.find(name);return it==flash.end()?File{}:File{&it->second};
 }
 bool rename(const char* from,const char* to){
  ++renames;if(!renameOk)return false;flash[to]=flash.at(from);flash.erase(from);return true;
 }
}LittleFS;
'''

STORAGE_DRIVER=r'''
void successAt(time_t epoch){
 btProtocolLastSyncEpoch[0]=btProfileLastSyncEpoch[0]=static_cast<uint32_t>(epoch);
 btProfileAddress[0]=btProfileLastSyncAddress[0]="aa:bb:cc:dd:ee:ff";
}
int main(){
 time_t epoch=1791858600;successAt(epoch);
 assert(saveBluetoothHistoryNow(epoch)&&writeOpens==1&&renames==1);
 const std::string saved=flash.at(BT_HISTORY_FILE);
 BtSyncHistory::Snapshot restored{};std::memcpy(&restored,saved.data(),sizeof(restored));
 assert(BtSyncHistory::valid(restored)&&restored.successEpoch==epoch);
 assert(restored.connections==3&&restored.notifications==5&&restored.responseErrors==1);
 for(int i=1;i<=1000;++i){successAt(epoch+i);assert(!saveBluetoothHistoryNow(epoch+i));}
 assert(writeOpens==1&&renames==1&&flash.at(BT_HISTORY_FILE)==saved);
 // Toggling retention never buys a second write on the current Brisbane day.
 btHistoryPersistEnabled=false;assert(!saveBluetoothHistoryNow(epoch+1200));
 btHistoryPersistEnabled=true;assert(!saveBluetoothHistoryNow(epoch+1200)&&writeOpens==1);
 // A restored snapshot quota prevents another write after a reboot.
 btHistorySavedDay=restored.savedDay;btHistoryAttemptDay=-1;
 assert(!saveBluetoothHistoryNow(epoch+1201)&&writeOpens==1);
 // Each failed first-success save consumes one RAM allowance and retains the old file.
 for(int fault=0;fault<4;++fault){
  epoch+=86400;successAt(epoch);
  openOk=fault!=0;shortWrite=fault==1;corruptWrite=fault==2;renameOk=fault!=3;
  const int before=writeOpens;
  assert(!saveBluetoothHistoryNow(epoch));assert(writeOpens==before+1);
  assert(flash.at(BT_HISTORY_FILE)==saved);
  for(int i=0;i<1000;++i)assert(!saveBluetoothHistoryNow(epoch+1));
  assert(writeOpens==before+1);
 }
 openOk=renameOk=true;shortWrite=corruptWrite=false;
 epoch+=86400;successAt(epoch);assert(saveBluetoothHistoryNow(epoch));
 std::memcpy(&restored,flash.at(BT_HISTORY_FILE).data(),sizeof(restored));
 assert(BtSyncHistory::valid(restored)&&restored.successEpoch==epoch);
 // Invalid snapshot identities fail before storage; no runtime retries follow.
 epoch+=86400;successAt(epoch);btProfileLastSyncAddress[0]="11:22:33:44:55:66";
 const int opens=writeOpens;assert(!saveBluetoothHistoryNow(epoch)&&writeOpens==opens);
 assert(!saveBluetoothHistoryNow(epoch+1)&&writeOpens==opens);
 std::puts("Actual daily snapshot: immediate first success, reboot/toggle quota, open/short/readback/rename faults and zero repeated writes passed");
}
'''

class StoragePolicyTest(unittest.TestCase):
    def test_actual_daily_snapshot_faults_keep_prior_file_and_quota(self):
        source=FIRMWARE.read_text()
        run_cpp(MOCKS+STORAGE_MOCKS+extract_function(source,'saveBluetoothHistoryNow')+STORAGE_DRIVER)

    def test_runtime_metadata_does_not_leak_into_configuration(self):
        source=FIRMWARE.read_text()
        writer=extract_function(source,'writeConfigNow')
        self.assertNotRegex(writer,r'bt(?:LastSyncEpoch|LastOutcomeSuccessful|RecentSyncs|BatteryReadings|ConnectionAttempts|Notifications|ResponseErrors)')
        loop=extract_function(source,'loop')
        self.assertNotRegex(loop,r'LittleFS\.(?:open|write|remove|rename)')
        history=extract_function(source,'saveBluetoothHistoryNow')
        self.assertLess(history.index('btHistoryAttemptDay ='),history.index('LittleFS.open'))
        self.assertIn('!btHistoryPersistEnabled',history)
        failed=extract_function(source,'configSaveFailed')
        self.assertIn('configDirty = false',failed)
        self.assertIn('configStorageFault = true',failed)
        queue=extract_function(source,'saveConfig')
        self.assertRegex(queue,r'if\s*\(configStorageFault\)\s*return')
        self.assertNotRegex(source,r'(?i)LittleFS\.open\([^\n]*(?:log|crash)')

if __name__=='__main__':unittest.main()
