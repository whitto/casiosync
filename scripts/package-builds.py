#!/usr/bin/env python3
"""Package the exact board builds, bounded factory images and debug symbols."""
from pathlib import Path
import gzip, hashlib, json, os, shutil, struct, subprocess, zipfile
root=Path(__file__).resolve().parents[1]
tools=Path(os.environ.get('RADIOCLOCK_TOOLS_DIR','/workspace/.radioclock-tools'))
esptool=tools/'data/packages/esp32/tools/esptool_py/5.3.1/esptool'
source=root/'firmware/CasioSync_V0_1/CasioSync_V0_1.ino'
import re
version=re.search(r'#define FIRMWARE_VERSION "([^"]+)"',source.read_text()).group(1)
build=re.search(r'#define FIRMWARE_BUILD "([^"]+)"',source.read_text()).group(1)
name=f'CasioSync_{version}_{build}'
release=root/'compiled'/f'{version}-{build}'
archive_dir=Path('/tmp/casiosync-release-assets');archive_dir.mkdir(exist_ok=True)
boot_app=tools/'data/packages/esp32/hardware/esp32/3.3.12/tools/partitions/boot_app0.bin'
configs={
 'node32s':{'chip':'esp32','label':'Node32s','boot_offset':0x1000,'fqbn':'esp32:esp32:node32s:FlashFreq=40,PartitionScheme=no_ota,EraseFlash=none','led':'GPIO2 active high','expected_chip_id':0},
 'esp32c3':{'chip':'esp32c3','label':'ESP32-C3_SuperMini','boot_offset':0,'fqbn':'esp32:esp32:esp32c3:FlashSize=4M,FlashMode=dio,FlashFreq=40,PartitionScheme=huge_app,CDCOnBoot=cdc,EraseFlash=none','led':'GPIO8 active low','expected_chip_id':5}}
# Hash publishable source paths only. Arduino's ignored firmware/build outputs
# can contain duplicate partition CSVs that are absent from GitHub source ZIPs.
source_paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z','--','firmware','libraries','ui'],cwd=root).decode().split('\0')
codefiles=sorted({root/p for p in source_paths if p and (root/p).is_file() and ((root/p).suffix in ('.ino','.h','.cpp','.c','.S','.csv','.html') or (root/p).name=='library.properties')})
source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in codefiles}
for board,meta in configs.items():
 out=tools/'output/CasioSync_V0_1'/board
 dest=release/board;dest.mkdir(parents=True,exist_ok=True)
 for original,new in [('CasioSync_V0_1.ino.bin','application.bin'),('CasioSync_V0_1.ino.bootloader.bin','bootloader.bin'),('CasioSync_V0_1.ino.partitions.bin','partitions.bin')]:shutil.copy2(out/original,dest/new)
 shutil.copy2(boot_app,dest/'boot_app0.bin')
 app=(dest/'application.bin').read_bytes()
 if app[0]!=0xe9 or struct.unpack_from('<H',app,12)[0]!=meta['expected_chip_id']:raise SystemExit('Wrong application chip image: '+board)
 parts=(dest/'partitions.bin').read_bytes();app_partition=None
 for offset in range(0,len(parts),32):
  item=parts[offset:offset+32]
  if len(item)<32 or item[:2]!=b'\xaaP':continue
  kind,subtype=item[2],item[3];start,size=struct.unpack_from('<II',item,4)
  if kind==0:app_partition=(start,size)
 if app_partition!=(0x10000,0x300000) or len(app)>app_partition[1]:raise SystemExit('Application does not fit shipped 3 MB partition: '+board)
 subprocess.run([str(esptool),'--chip',meta['chip'],'merge-bin','--output',str(dest/'factory.bin'),'--flash-mode','dio','--flash-freq','40m','--flash-size','4MB',hex(meta['boot_offset']),str(dest/'bootloader.bin'),'0x8000',str(dest/'partitions.bin'),'0xe000',str(dest/'boot_app0.bin'),'0x10000',str(dest/'application.bin')],check=True)
 if (dest/'factory.bin').stat().st_size>=0x310000:raise SystemExit('Factory image would overlap settings storage')
 # Keep matching symbols for crash decoding without publishing an uncompressed ELF.
 with (out/'CasioSync_V0_1.ino.elf').open('rb') as inp,(dest/'firmware.elf.gz').open('wb') as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as zipped:shutil.copyfileobj(inp,zipped)
 cmd=f'python -m esptool --chip {meta["chip"]} --port YOUR_PORT --baud 460800 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB {hex(meta["boot_offset"])} bootloader.bin 0x8000 partitions.bin 0xe000 boot_app0.bin 0x10000 application.bin'
 readme=f'''# {name} — {meta['label']}

Built for a 4 MB {meta['label']} using Arduino-ESP32 3.3.12. Activity LED: {meta['led']}. C3 uses native USB CDC. This package is for the stated chip; use the other package for the other board.

Install esptool 5.x (`python -m pip install esptool`) and run from this folder, replacing YOUR_PORT with the board's serial port:

```
{cmd}
```

For an application-only upgrade when this project's partition table is already installed:

```
python -m esptool --chip {meta['chip']} --port YOUR_PORT --baud 460800 write-flash 0x10000 application.bin
```

`factory.bin` is the merged first-install image at offset 0x0. It stops before LittleFS; it is not the CLI's padded 4 MB image. The separate-file command avoids writing the gaps containing SDK NVS. Neither command calls erase-flash. Application upgrades retain saved CasioSync settings. Boot/partition updates should use the separate images above.

After flashing, press Reset. A fresh setup uses Wi-Fi CasioSync_XXXXXX, password 12345678, browser http://192.168.4.1. A new/unformatted filesystem is retained for explicit Settings storage recovery rather than erased automatically. Existing Time Transmitter configuration has a different filename/schema; provision CasioSync separately.

If the port will not enter download mode automatically, hold BOOT while pressing/releasing RESET, then release BOOT and retry. Close Arduino Serial Monitor while uploading. Use a data-capable USB cable. The SuperMini package drives its discrete blue GPIO8 LED active-low; it is not the generic C3 RGB-LED build.

`manifest.json` records hashes, chip/flash settings, source hashes and exact validation limits. `firmware.elf.gz` contains the matching ELF for crash/backtrace decoding. These builds have not been flashed onto a physical board in this cloud environment.
'''
 (dest/'README.md').write_text(readme)
 manifest={'project':'whitto/casiosync','version':version,'build':build,'board':board,'chip':meta['chip'],'fqbn':meta['fqbn'],'compiler_cpp_extra_flags':'-DCASIOSYNC_C3_SUPERMINI=1' if board=='esp32c3' else '', 'arduino_esp32':'3.3.12','flash_size':4194304,'flash_frequency':'40MHz','flash_mode':'DIO','application_offset':0x10000,'application_partition_size':0x300000,'bootloader_offset':meta['boot_offset'],'factory_offset':0,'activity_led':meta['led'],'physical_board_tested':False,'physical_new_watch_features_tested':False,'source_sha256':source_hashes,'elf_sha256':hashlib.sha256((out/'CasioSync_V0_1.ino.elf').read_bytes()).hexdigest(),'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(dest.iterdir()) if p.is_file() and p.name!='manifest.json'}}
 (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=archive_dir/f'{name}_{meta["label"]}.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(dest.iterdir()):z.write(p,arcname=f'{name}_{meta["label"]}/{p.name}')
 print(f'Packaged {board}: {len(app)} application bytes; {archive}')
