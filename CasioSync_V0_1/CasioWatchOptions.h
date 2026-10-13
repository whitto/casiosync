#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "CasioWatchFeatures.h"
#include "CasioConfigWriter.h"

// User choices only, written after explicit UI Save. Numeric wire flags avoid
// reading corrupt bytes into C++ bool objects; integrity is checked before use.
namespace CasioWatchOptions {
constexpr uint32_t Magic=0x43574f31U; // CWO1
constexpr uint32_t Schema=1;
constexpr size_t ProfileCount=4;
struct AlarmRecord { uint8_t enabled,hour,minute; };
struct ProfileRecord {
  char address[18]; uint8_t protocol;
  uint8_t enabled,alarmsEnabled;
  AlarmRecord alarms[5];
  int8_t hourlyChime;
  uint8_t timerEnabled;
  uint32_t timerSeconds;
  uint8_t basicMask,basicValues,language;
  uint8_t autoAdjustEnabled,autoAdjust,autoAdjustMinute;
};
struct Snapshot {
  uint32_t magic,schema,size,checksum;
  ProfileRecord profiles[ProfileCount];
};
inline bool addressValid(const char (&value)[18]) {
  if (!memchr(value,'\0',sizeof(value))) return false;
  if (!value[0]) return true;
  if (value[17]) return false;
  for (size_t i=0;i<17;++i) {
    const char c=value[i];
    if (i%3==2) { if (c!=':') return false; }
    else if (!((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F'))) return false;
  }
  return true;
}
inline bool recordValid(const ProfileRecord &record) {
  if (!addressValid(record.address)||record.protocol>2||record.enabled>1||record.alarmsEnabled>1||
      record.hourlyChime < -1 || record.hourlyChime>1 || record.timerEnabled>1 ||
      record.timerSeconds<1 || record.timerSeconds>86400 || record.basicMask>127 ||
      record.basicValues>63 || record.language>5 || record.autoAdjustEnabled>1 ||
      record.autoAdjust>1 || record.autoAdjustMinute>59 || (record.enabled && !record.address[0])) return false;
  for (const AlarmRecord &alarm:record.alarms)
    if (alarm.enabled>1||alarm.hour>23||alarm.minute>59) return false;
  return true;
}
inline uint32_t checksum(const Snapshot &snapshot) {
  Snapshot copy;
  memcpy(&copy,&snapshot,sizeof(copy)); // Hash the stored bytes, including padding.
  copy.checksum=0;
  return CasioConfigFormat::crc32(reinterpret_cast<const char *>(&copy),sizeof(copy));
}
inline bool valid(const Snapshot &snapshot) {
  if (snapshot.magic!=Magic || snapshot.schema!=Schema || snapshot.size!=sizeof(snapshot) ||
      snapshot.checksum!=checksum(snapshot)) return false;
  for (const ProfileRecord &record:snapshot.profiles) if (!recordValid(record)) return false;
  return true;
}
inline void seal(Snapshot &snapshot) {
  snapshot.magic=Magic; snapshot.schema=Schema; snapshot.size=sizeof(snapshot);
  snapshot.checksum=0; snapshot.checksum=checksum(snapshot);
}
inline void encode(const CasioWatchFeatures::Desired &desired,const char *address,uint8_t protocol,ProfileRecord &record) {
  memset(&record,0,sizeof(record));
  if (address) {
    const size_t n=strlen(address);
    if (n<sizeof(record.address)) memcpy(record.address,address,n+1);
  }
  record.protocol=protocol; record.enabled=desired.enabled; record.alarmsEnabled=desired.alarmsEnabled;
  for (size_t i=0;i<5;++i) record.alarms[i]={static_cast<uint8_t>(desired.alarms[i].enabled),desired.alarms[i].hour,desired.alarms[i].minute};
  record.hourlyChime=desired.hourlyChime; record.timerEnabled=desired.timerEnabled; record.timerSeconds=desired.timerSeconds;
  record.basicMask=desired.basicMask;
  record.basicValues=(desired.timeFormat24?1:0)|(desired.buttonTone?2:0)|(desired.autoLight?4:0)|
                     (desired.powerSaving?8:0)|(desired.longLight?16:0)|(desired.dateDayFirst?32:0);
  record.language=desired.language; record.autoAdjustEnabled=desired.autoAdjustEnabled;
  record.autoAdjust=desired.autoAdjust; record.autoAdjustMinute=desired.autoAdjustMinute;
}
inline CasioWatchFeatures::Desired decode(const ProfileRecord &record) {
  CasioWatchFeatures::Desired desired{};
  desired.enabled=record.enabled; desired.alarmsEnabled=record.alarmsEnabled;
  for (size_t i=0;i<5;++i) {
    desired.alarms[i].enabled=record.alarms[i].enabled;
    desired.alarms[i].hour=record.alarms[i].hour; desired.alarms[i].minute=record.alarms[i].minute;
  }
  desired.hourlyChime=record.hourlyChime; desired.timerEnabled=record.timerEnabled; desired.timerSeconds=record.timerSeconds;
  desired.basicMask=record.basicMask; desired.timeFormat24=record.basicValues&1; desired.buttonTone=record.basicValues&2;
  desired.autoLight=record.basicValues&4; desired.powerSaving=record.basicValues&8;
  desired.longLight=record.basicValues&16; desired.dateDayFirst=record.basicValues&32;
  desired.language=record.language; desired.autoAdjustEnabled=record.autoAdjustEnabled;
  desired.autoAdjust=record.autoAdjust; desired.autoAdjustMinute=record.autoAdjustMinute;
  return desired;
}
}
