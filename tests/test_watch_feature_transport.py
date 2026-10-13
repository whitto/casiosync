#!/usr/bin/env python3
"""Exercise production optional-setting transport with bounded watch replies.

Physical watch behavior remains separate. This fixture runs the real feature
executor, notification routing and readback checks with ATT operations mocked.
"""
import unittest
import subprocess

import support as workflow
from test_watch_battery import NOTIFICATION_MOCKS


FEATURE_MOCKS = r'''
#include "CasioWatchFeatures.h"
#include <map>
#define CASIO_BASIC_REQUEST_CHAR "basic-request"
constexpr size_t BT_RESPONSE_CAPACITY=512;
constexpr int BT_WATCH_PROFILE_COUNT=4;
uint8_t btActiveProfile=0,btActiveProtocol=0,btFontMode[4]={};
String btLastWatchName="GW-BX5600",btLastWatchAddress="aa:bb:cc:dd:ee:ff";
String btProfileName[4];
CasioWatchFeatures::Desired btFeatureDesired[4];
char btFeatureBoundAddress[4][18]={};uint8_t btFeatureBoundProtocol[4]={};
const char* btFeatureStatus[4]={};const char* btGattStage="idle";
NimBLERemoteCharacteristic featureRequest{CASIO_BASIC_REQUEST_CHAR};
bool missingRequest=false;
struct NimBLERemoteService {
  NimBLERemoteCharacteristic* getCharacteristic(NimBLEUUID uuid) {
    assert(uuid.uuid==CASIO_BASIC_REQUEST_CHAR);
    return missingRequest?nullptr:&featureRequest;
  }
} service;
NimBLERemoteService* btService=&service;
NimBLERemoteCharacteristic* btSetChar=&allFeatures;
std::map<uint8_t,std::vector<uint8_t>> watch;
std::vector<uint8_t> requested,written;
bool failWrite=false,staleReadback=false,timeoutReply=false,wrongChannel=false;
bool disconnectOnRequest=false;
uint32_t requestDelay=0,writeDelay=0;
static void gshockNotifyCallback(NimBLERemoteCharacteristic*,uint8_t*,size_t,bool);
bool writeBt(NimBLERemoteCharacteristic* characteristic,const uint8_t* data,size_t size,bool response) {
  if(btTransactionCancelled()||!btClientConnected||!btClientPreemptionEnabled)return false;
  if(characteristic==&featureRequest) {
    assert(!response&&size==1&&btResponseActive&&btExpectedHeader==data[0]);
    requested.push_back(data[0]);delay(requestDelay);
    if(disconnectOnRequest){btClientConnected=false;return false;}
    if(!timeoutReply) {
      auto& packet=watch.at(data[0]);
      gshockNotifyCallback(wrongChannel?&spData:&allFeatures,packet.data(),packet.size(),true);
    }
    return true;
  }
  assert(characteristic==&allFeatures&&response&&size>=5&&size<=17);
  written.push_back(data[0]);delay(writeDelay);
  if(failWrite)return false;
  if(!staleReadback)watch[data[0]]=std::vector<uint8_t>(data,data+size);
  return true;
}
void resetFeatures(uint32_t start=0) {
  reset(start);btTransactionActive=true;btTransactionStartedMillis=start;
  btActiveProfile=btActiveProtocol=0;btLastWatchName="GW-BX5600";
  btLastWatchAddress="aa:bb:cc:dd:ee:ff";
  btService=&service;btSetChar=&allFeatures;
  missingRequest=failWrite=staleReadback=timeoutReply=wrongChannel=disconnectOnRequest=false;
  featureRequest.noResponse=allFeatures.notify=allFeatures.subscribeOk=true;
  allFeatures.indicate=false;allFeatures.subscriptions=0;
  requestDelay=writeDelay=0;requested.clear();written.clear();watch.clear();
  // Captured BX-compatible basic/auto-adjust/timer shapes and shared alarm records.
  watch[0x15]={0x15,0x13,0x00,0x06,0x2d};
  watch[0x16]={0x16,0x13,0,8,0,0x13,0,12,0,0x13,0,9,0,0x13,0,9,25};
  watch[0x18]={0x18,0,6,0,0,0,0,0,0,0,0,0,0,0,0};
  watch[0x13]={0x13,0,1,0,0,0,0,0,0,0,0,0};
  watch[0x11]={0x11,0x0f,0x0f,0x0f,6,0,0x50,0,4,0,1,0,0,30,3};
  for(unsigned profile=0;profile<4;++profile) {
    btFeatureDesired[profile]={};btFontMode[profile]=0;btProfileName[profile]="GW-BX5600";
    std::strcpy(btFeatureBoundAddress[profile],"aa:bb:cc:dd:ee:ff");
    btFeatureBoundProtocol[profile]=0;btFeatureStatus[profile]="Not attempted";
  }
}
void timerSelection(){auto& d=btFeatureDesired[0];d.enabled=d.timerEnabled=true;d.timerSeconds=3661;}
bool statusHas(const char* text){return std::strstr(btFeatureStatus[0],text)!=nullptr;}
'''


FEATURE_DRIVER = r'''
int main() {
  // Every new basic-feature response must use TIME/all-features, including
  // its unheaded continuation; legacy SP headers retain their SP_DATA route.
  for(uint8_t header : {uint8_t(0x15),uint8_t(0x16),uint8_t(0x18),uint8_t(0x13),uint8_t(0x11)}) {
    resetFeatures();auto packet=watch.at(header);prepareBtResponse(header);
    gshockNotifyCallback(&spData,packet.data(),packet.size(),true);
    assert(btResponseLength==0);
    uint8_t unrelatedHeader[]={0xff,0};
    gshockNotifyCallback(&allFeatures,unrelatedHeader,sizeof(unrelatedHeader),true);
    assert(btResponseLength==0);
    gshockNotifyCallback(&allFeatures,packet.data(),2,true);
    gshockNotifyCallback(&spData,packet.data()+2,packet.size()-2,true);
    assert(btResponseLength==2);
    gshockNotifyCallback(&allFeatures,packet.data()+2,packet.size()-2,true);
    assert(btResponseLength==packet.size()&&waitBt(packet.size(),1200));
  }
  for(uint8_t header : {uint8_t(0x05),uint8_t(0x03),uint8_t(0x06)}) {
    resetFeatures();uint8_t packet[]={header,1,2,3};prepareBtResponse(header);
    gshockNotifyCallback(&allFeatures,packet,sizeof(packet),true);assert(btResponseLength==0);
    gshockNotifyCallback(&spData,packet,sizeof(packet),true);
    assert(btResponseLength==sizeof(packet)&&waitBt(sizeof(packet),1200));
  }
  resetFeatures();applyBluetoothWatchFeatures();
  assert(requested.empty()&&written.empty()&&statusHas("Off"));
  resetFeatures();btFeatureDesired[0].enabled=true;applyBluetoothWatchFeatures();
  assert(requested.empty()&&statusHas("No optional"));
  for(int rejection=0;rejection<5;++rejection) {
    resetFeatures();timerSelection();
    if(rejection==0)btLastWatchAddress="11:22:33:44:55:66";
    if(rejection==1)btFeatureBoundProtocol[0]=1;
    if(rejection==2)btLastWatchName="unknown watch";
    if(rejection==3)btLastWatchName="MTG-B3000";
    if(rejection==4)btFeatureDesired[0].timerSeconds=86401;
    applyBluetoothWatchFeatures();assert(requested.empty()&&written.empty()&&statusHas("Skipped"));
  }
  resetFeatures();timerSelection();btLastWatchName="GA-B2100";
  applyBluetoothWatchFeatures();assert(requested.empty()&&statusHas("Skipped")); // This model's 1-hour timer limit.
  resetFeatures();btActiveProfile=255;applyBluetoothWatchFeatures();assert(requested.empty());
  // Five optional groups are read/merged/read back separately before TIME.
  resetFeatures();auto& desired=btFeatureDesired[0];
  desired.enabled=desired.alarmsEnabled=desired.timerEnabled=desired.autoAdjustEnabled=true;
  desired.hourlyChime=1;desired.timerSeconds=3661;desired.basicMask=CasioWatchFeatures::kTimeFormat;
  desired.timeFormat24=true;desired.autoAdjust=false;desired.autoAdjustMinute=59;
  for(unsigned i=0;i<5;++i)desired.alarms[i]={true,uint8_t(7+i),uint8_t(10+i)};
  const auto original=watch;applyBluetoothWatchFeatures();
  assert((written==std::vector<uint8_t>{0x15,0x16,0x18,0x13,0x11}));
  assert(requested.size()==10&&elapsed==3000&&statusHas("confirmed by watch readback"));
  assert(watch[0x15][2]==original.at(0x15)[2]&&(watch[0x15][1]&0x3f)==0x13);
  assert(watch[0x18][4]==original.at(0x18)[4]&&watch[0x13][8]==original.at(0x13)[8]);
  assert(watch[0x11][0]==original.at(0x11)[0]&&watch[0x11][14]==original.at(0x11)[14]);
  requested.clear();written.clear();applyBluetoothWatchFeatures();
  assert(requested.size()==5&&written.empty()&&statusHas("confirmed by watch readback"));
  // Settings already matching the watch require no optional flash or ATT write.
  resetFeatures();timerSelection();btFeatureDesired[0].timerSeconds=360;
  applyBluetoothWatchFeatures();assert(requested.size()==1&&written.empty()&&statusHas("confirmed"));
  for(int fault=0;fault<6;++fault) {
    resetFeatures();timerSelection();
    if(fault==0)timeoutReply=true;
    if(fault==1)watch[0x18].pop_back();
    if(fault==2)wrongChannel=true;
    if(fault==3)failWrite=true;
    if(fault==4)staleReadback=true;
    if(fault==5)disconnectOnRequest=true;
    applyBluetoothWatchFeatures();assert(statusHas("failed")&&!btResponseActive);
    assert(!statusHas("confirmed by watch readback"));
    if(fault<3)assert(written.empty());
  }
  for(int unavailable=0;unavailable<4;++unavailable) {
    resetFeatures();timerSelection();
    if(unavailable==0)missingRequest=true;
    if(unavailable==1)featureRequest.noResponse=false;
    if(unavailable==2)allFeatures.notify=false;
    if(unavailable==3)allFeatures.subscribeOk=false;
    applyBluetoothWatchFeatures();assert(requested.empty()&&written.empty()&&statusHas("unavailable"));
  }
  // Optional admission and post-read checks preserve final TIME/font reserves.
  resetFeatures();timerSelection();tick=34000;applyBluetoothWatchFeatures();
  assert(requested.empty()&&statusHas("Deferred")&&btTransactionRemainingMs()==11000);
  resetFeatures();timerSelection();btFontMode[0]=1;tick=25000;
  applyBluetoothWatchFeatures();assert(requested.empty()&&btTransactionRemainingMs()==20000);
  resetFeatures();timerSelection();tick=33500;requestDelay=3000;
  applyBluetoothWatchFeatures();assert(requested.size()==1&&written.empty()&&statusHas("Deferred"));
  assert(btTransactionRemainingMs()>=5000);
  // Remaining time and bounded notification waits survive target millis wrap.
  resetFeatures(UINT32_MAX-100);timerSelection();applyBluetoothWatchFeatures();
  assert(written.size()==1&&requested.size()==2&&elapsed==600&&statusHas("confirmed"));
  std::puts("Actual optional-feature executor: identity/model guards, read/merge/readback, unchanged bytes, failure paths, TIME/font reserves and rollover passed");
}
'''


class WatchFeatureTransportTest(unittest.TestCase):
    def test_production_feature_executor_and_time_budget(self):
        source = workflow.FIRMWARE.read_text()
        string_mock = workflow.balanced_block(workflow.MOCKS, workflow.MOCKS.index('class String')) + ';'
        # Production timestamps are 32-bit on ESP32, including after millis wrap.
        functions = '\n'.join(workflow.extract_function(source, name) for name in
                              ('btTransactionRemainingMs', 'optionalReplyTimeoutMs',
                               'cancelBtResponse', 'gshockNotifyCallback', 'prepareBtResponse',
                               'waitBt', 'copyBt', 'readWatchFeature', 'featureReplyMatches',
                               'mergeFeatureReply', 'applyBluetoothWatchFeatures'))
        functions = functions.replace('unsigned long last =', 'uint32_t last =')
        try:
            result = workflow.run_cpp(NOTIFICATION_MOCKS + string_mock +
                                      workflow.transaction_deadline_source(source) + FEATURE_MOCKS + functions + FEATURE_DRIVER)
        except subprocess.CalledProcessError as failure:
            self.fail(failure.stderr or str(failure))
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
