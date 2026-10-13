#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
 const html=await fs.readFile(path.join(__dirname,'../ui/casiosync.html'),'utf8');
 const firmware=await fs.readFile(path.join(__dirname,'../firmware/CasioSync_V0_1/CasioSync_V0_1.ino'),'utf8');
 const version=firmware.match(/#define FIRMWARE_VERSION "([^"]+)"/)[1],build=firmware.match(/#define FIRMWARE_BUILD "([^"]+)"/)[1];
 const renderOnly=process.argv.includes('--render-only');
 const desired={enabled:false,alarms_enabled:false,alarms:Array.from({length:5},()=>({enabled:false,hour:7,minute:0})),hourly_chime:-1,timer_enabled:false,timer_seconds:300,basic_mask:0,time_format_24:true,button_tone:true,auto_light:false,power_saving:true,long_light:false,date_day_first:true,language:0,auto_adjust_enabled:false,auto_adjust:true,auto_adjust_minute:30};
 const caps={basic_mask:127,alarms:true,hourly_chime:true,timer:true,timer_max_seconds:86400,auto_adjust:true};
 const profiles=[
  {id:0,bound:true,name:'CASIO GW-BX5600',address:'11:22:33:44:55:66',protocol:0,font_mode:1,battery_percent:80,battery_read_at:'2026-10-13 06:30:12',battery_status:'Read during sync',feature_desired:structuredClone(desired),feature_capabilities:caps,feature_status:'No optional settings requested.'},
  {id:1,bound:true,name:'CASIO GW-B5600',address:'22:33:44:55:66:77',protocol:1,font_mode:0,feature_desired:structuredClone(desired),feature_capabilities:caps,feature_status:'No optional settings requested.'},
  {id:2,bound:true,name:'CASIO MTG-B3000',address:'33:44:55:66:77:88',protocol:2,font_mode:0,feature_desired:structuredClone(desired),feature_capabilities:{basic_mask:0},feature_status:'Unavailable for this protocol.'},
  {id:3,bound:false,name:'',address:'',protocol:0,font_mode:0,feature_desired:structuredClone(desired),feature_capabilities:{basic_mask:0},feature_status:'Pair a supported watch first.'}];
 const config={ssid:'Home',timezone:'Australia/Brisbane',bt_timezone:'Australia/Brisbane',bt_time_offset_minutes:0,wifi_power_mode:0,bt_manual_profile:0,bt_manual_protocol:0,bt_always_wait:true,bt_idle_power_save:false,activity_led_enabled:true,bt_history_persist:true,crash_dump_enabled:false,crash_dump_available:true,filesystem_available:true,config_storage_fault:false,bt_profiles:profiles,bt_times:[30,390,750,1110].map(minute=>({minute,enabled:true,profile:0,protocol:0})),wifi_access_enabled:false,wifi_access_start:1080,wifi_access_end:1200,wifi_access_timezone:'Australia/Brisbane'};
 const recent=[{successful:true,date:'2026-10-13 06:30:12',protocol:0},{successful:false,date:'2026-10-12 18:30:05',protocol:0},{successful:true,date:'2026-10-12 12:30:14',protocol:0},{successful:true,date:'2026-10-12 06:30:10',protocol:0}];
 const status={...config,firmware_version:version,firmware_build:build,time:'09:15:42',local_time:'09:15:42',date:'2026-10-13',bt_time:'2026-10-13 09:15:42',clock_state:'Synchronized',wifi_connected:true,ap_mode:false,wifi_ip:'10.0.1.137',bt_state:'Scanning',bt_day_complete:true,ntp_age_sec:60,clock_error_est_sec:.2012,littlefs_used:12288,littlefs_total:917504,bt_connection_attempts:4,bt_acked_writes:30,bt_response_errors:0,uptime_sec:93784,heap_free:110000,bt_last_sync_status:'Watch 1: GW-BX5600 MIP - time write delivered (watch unverified)',bt_last_sync_date:'2026-10-13 06:30:12',bt_last_outcome_successful:true,bt_recent_sync_profile:0,bt_recent_syncs:recent,bt_font_status:'Standard font confirmed by settings readback'};
 const diagnostics={firmware:version,firmware_build:build,uptime_sec:93784,reset_reason:1,heap_free:110000,heap_min_free:80000,heap_max_alloc:65000,loop_stack_min_free:5000,led_stack_min_free:1300,monitor_stack_min_free:1400,clock_state:'Synchronized',ntp_age_sec:60,clock_error_est_sec:.2012,ntp_sync_count:4,ntp_candidate_replies:0,ntp_reacquisitions:0,ntp_interval_sec:3600,wifi_connected:true,ap_mode:false,wifi_ip:'10.0.1.137',wifi_power_requested:true,wifi_power_observed:true,wifi_power_fault:false,wifi_power_fault_count:0,filesystem_available:true,littlefs_used:12288,littlefs_total:917504,bt_window_active:true,bt_connection_attempts:4,bt_acked_writes:30,bt_notifications:20,bt_response_errors:0,bt_last_sync_date:status.bt_last_sync_date,bt_last_sync_status:status.bt_last_sync_status,bt_last_outcome_successful:true,bt_history_persist:true,bt_delivery_evidence:'ATT write acknowledged; watch display unverified'};
 const server=http.createServer((req,res)=>{res.writeHead(200,{'content-type':'text/html'});res.end(html)});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser,rejectFeature=false,holdFeature=false,releaseFeature;
 const requests=[],errors=[];
 try{
  browser=await chromium.launch({executablePath:process.env.CASIOSYNC_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  await page.addInitScript(()=>{window.setInterval=()=>0});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url()).pathname,method=req.method();
   const fields=req.headers()['content-type']?.includes('application/json')?JSON.parse(req.postData()||'{}'):Object.fromEntries([...(req.postData()||'').matchAll(/name="([^"]+)"\r\n\r\n([^\r\n]*)/g)].map(x=>[x[1],x[2]]));
   requests.push({url,method,fields});let data={},code=200;
   if(url==='/api/watch-settings'&&method==='POST'){
    if(holdFeature){holdFeature=false;await new Promise(resolve=>releaseFeature=resolve)}
    if(rejectFeature){rejectFeature=false;code=500;data={status:'error',message:'Watch settings could not be saved'}}
    else {const {profile,...settings}=fields;profiles[Number(profile)].feature_desired=settings;data={status:'ok'}}
   }else if((url==='/api/config'||url==='/api/settings')&&method==='POST'){
    if('bt_slot' in fields){const slot=config.bt_times[Number(fields.bt_slot)];for(const [key,name] of Object.entries({bt_slot_time:'minute',bt_slot_enabled:'enabled',bt_slot_protocol:'protocol',bt_slot_profile:'profile'}))if(key in fields)slot[name]=name==='enabled'?fields[key]==='1':Number(fields[key])}
    else for(const [key,value]of Object.entries(fields)){if(['bt_always_wait','activity_led_enabled','bt_idle_power_save','bt_history_persist','crash_dump_enabled','wifi_access_enabled'].includes(key))config[key]=value==='1'||value==='true';else if(['bt_time_offset_minutes','bt_manual_profile','bt_manual_protocol','wifi_power_mode','wifi_access_start','wifi_access_end'].includes(key))config[key]=Number(value);else config[key]=value}
    if(config.wifi_access_enabled)config.wifi_power_mode=1;data={status:'ok'};
   }else if(url==='/api/config')data=config;
   else if(url==='/api/status')data={...status,...config,bt_profiles:profiles,bt_recent_sync_profile:config.bt_manual_profile,bt_recent_syncs:config.bt_manual_profile===0?recent:[]};
   else if(url==='/api/diagnostics')data=diagnostics;
   else if(['/api/ntp-sync','/api/bluetooth-pair','/api/bluetooth-sync','/api/storage/reset'].includes(url))data={status:'ok',message:'Requested'};
   else {code=404;data={status:'error',message:'Unknown route '+url}}
   await route.fulfill({status:code,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.waitForFunction(label=>document.getElementById('fw').textContent===label&&document.querySelectorAll('#btScheduleList .slot').length===4,version+' '+build);
  assert.deepEqual(await page.locator('.navbtn').allTextContents(),['Overview','Watches','Schedules','Network','Settings','Diagnostics','About']);
  assert.equal(await page.locator('#projectHeaderLink').getAttribute('href'),'https://github.com/whitto/casiosync');
  assert.equal(await page.locator('#projectAboutLink').getAttribute('href'),'https://github.com/whitto/casiosync');
  await fs.mkdir(path.join(__dirname,'../docs/build-evidence/v0.1'),{recursive:true});
  await page.screenshot({path:path.join(__dirname,'../docs/build-evidence/v0.1/overview-desktop.png'),fullPage:true});
  await page.evaluate(()=>showView('watch'));
  assert.equal(await page.locator('#watchFeaturesEnabled').isChecked(),false);
  assert.equal(await page.locator('#watchAlarmsEnabled').isDisabled(),true);
  await page.screenshot({path:path.join(__dirname,'../docs/build-evidence/v0.1/watches-desktop.png'),fullPage:true});
  // Show a sample alarm draft for README screenshots without saving it.
  await page.locator('#watchFeaturesEnabled').check();await page.locator('#watchAlarmsEnabled').check();
  await page.locator('#watchAlarmTime0').fill('06:45');await page.locator('#watchAlarmTime0').dispatchEvent('change');await page.locator('#watchAlarmOn0').check();
  await page.locator('#watchBasicGroup').screenshot({path:path.join(__dirname,'../docs/build-evidence/v0.1/watch-settings-desktop.png')});
  await page.locator('#watchAlarmGroup').screenshot({path:path.join(__dirname,'../docs/build-evidence/v0.1/alarms-desktop.png')});
  await page.evaluate(()=>{watchFeatureDrafts[0]=null;watchFeatureShownProfile=-1;renderWatchFeatures()});
  assert.equal(await page.locator('#watchFeaturesEnabled').isChecked(),false,'screenshot draft reset');
  if(!renderOnly){
   await page.evaluate(async()=>{await setBtAlwaysWait(false)});assert.equal(config.bt_always_wait,false);
   await page.evaluate(async()=>{await setBtSlot(2,false)});assert.equal(config.bt_times[2].enabled,false);
   await page.evaluate(async()=>{await setBtTimezone('Asia/Tokyo');await setBtTimeOffset(30)});assert.equal(config.bt_timezone,'Asia/Tokyo');assert.equal(config.bt_time_offset_minutes,30);
   await page.evaluate(()=>showView('watch'));
   await page.locator('#watchFeaturesEnabled').check();await page.locator('#watchAlarmsEnabled').check();
   await page.locator('#watchAlarmTime0').fill('06:45');await page.locator('#watchAlarmTime0').dispatchEvent('change');await page.locator('#watchAlarmOn0').check();
   await page.locator('#watchBasic_time_format_24').selectOption('0');await page.evaluate(()=>pollStatus());
   assert.equal(await page.locator('#watchAlarmTime0').inputValue(),'06:45');
   await page.evaluate(async()=>{await setBtManualProfile(1)});await page.evaluate(async()=>{await setBtManualProfile(0)});
   assert.equal(await page.locator('#watchAlarmTime0').inputValue(),'06:45','profile draft preserved');
   await page.evaluate(async()=>{await saveWatchFeatures()});assert.equal(profiles[0].feature_desired.alarms[0].hour,6);assert.equal(profiles[0].feature_desired.alarms[0].minute,45);assert.equal(profiles[0].feature_desired.alarms[0].enabled,true);
   const before=structuredClone(profiles[0].feature_desired);rejectFeature=true;
   await page.locator('#watchAlarmTime0').fill('07:45');await page.locator('#watchAlarmTime0').dispatchEvent('change');await page.evaluate(async()=>{await saveWatchFeatures()});assert.deepEqual(profiles[0].feature_desired,before);
   assert.equal(await page.locator('#watchAlarmTime0').inputValue(),'07:45','failed-save draft retained');
   await page.evaluate(async()=>{await setBtManualProfile(2)});
   const analogueState=await page.evaluate(()=>({profile:selectedProfile(),manual:config.bt_manual_profile,caps:watchFeaturesCaps(),watch:watchFeaturesProfile().name,masterHidden:document.getElementById('watchFeaturesMasterRow').hidden,masterDisplay:getComputedStyle(document.getElementById('watchFeaturesMasterRow')).display}));
   assert.equal(await page.locator('#watchFeaturesMasterRow').isHidden(),true,'analogue optional settings hidden: '+JSON.stringify(analogueState));assert.equal(await page.locator('#watchFeaturesSave').isHidden(),true,'no unsupported settings save control');
   await page.evaluate(async()=>{await setBtManualProfile(0)});
   await page.evaluate(async()=>{showView('settings');await setBtHistoryPersist(false);await setCrashDumpEnabled(true)});assert.equal(config.bt_history_persist,false);assert.equal(config.crash_dump_enabled,true);
   await page.locator('#wifiAccessStart').fill('23:00');await page.locator('#wifiAccessStart').dispatchEvent('input');await page.locator('#wifiAccessEnd').fill('01:00');await page.locator('#wifiAccessEnd').dispatchEvent('input');await page.locator('#wifiAccessEnabled').check();await page.waitForFunction(()=>!document.getElementById('wifiAccessSave').disabled);assert.equal(config.wifi_access_start,1380);assert.equal(config.wifi_access_end,60);assert.equal(config.wifi_power_mode,1);
   await page.evaluate(async()=>{showView('advanced');await updateDiagnostics(true)});
   assert.match(await page.locator('#diagnostics').textContent(),/26h 03m 04s/);
   assert.ok(!requests.some(x=>/stations|radio|schedules$/.test(x.url)),'No LF API requests');
  }
  await page.evaluate(()=>{showView('home');applyTheme('light')});await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'phone fits viewport');
  await page.screenshot({path:path.join(__dirname,'../docs/build-evidence/v0.1/overview-phone.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log(renderOnly?'PASS focused CasioSync desktop/watch/phone render; seven-page sidebar, no LF routes, opt-in feature controls':'PASS CasioSync browser regressions: seven-page sidebar, daily BT/tz edits, per-profile alarm drafts/saves/failure rollback, analogue capability guard, Wi-Fi schedule, independent flash toggles, h/m/s uptime and phone layout');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve))}
})().catch(error=>{console.error(error);process.exitCode=1});
