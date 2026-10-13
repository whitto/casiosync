#!/usr/bin/env python3
"""Check Casio-only assets, routes, versions and pinned partition layout."""
from pathlib import Path
from html.parser import HTMLParser
import gzip, re, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
sketch=root/"firmware/CasioSync_V0_1"
source=(sketch/"CasioSync_V0_1.ino").read_text()
html=(root/"ui/casiosync.html").read_text()
version=re.search(r'#define FIRMWARE_VERSION "([^"]+)"',source).group(1)
build=re.search(r'#define FIRMWARE_BUILD "([^"]+)"',source).group(1)
assert version=="V0.1" and version+" "+build in html
for forbidden in ('radioTask','stationTime(', 'ampchange(', 'mb_jjy(', 'full_time_tx', 'transmission_offset_minutes', '/api/stations', '/api/radio'):
    assert forbidden not in source and forbidden not in html, forbidden
for required in ('bt_timezone','bt_time_offset_minutes','wifi_access_enabled','bt_idle_power_save','bt_history_persist'):
    assert required in source and required in html, required
assert "bluetoothLocalTime(" in source and "bt_time" in html
asset=re.search(r'INDEX_HTML_GZ\[\] PROGMEM = \{(.*?)\n\};',source,re.S)
assert asset, "Missing embedded UI"
compressed=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',asset[1]))
assert gzip.decompress(compressed)==html.encode(), "Embedded UI is stale"
class Elements(HTMLParser):
    def __init__(self): super().__init__(); self.ids=[]
    def handle_starttag(self,tag,attrs):
        self.ids.extend(v for k,v in attrs if k=="id")
elements=Elements(); elements.feed(html)
assert len(elements.ids)==len(set(elements.ids)), "Duplicate DOM IDs"
refs=set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)",html))
assert refs<=set(elements.ids), f"Missing DOM IDs: {refs-set(elements.ids)}"
routes=set(re.findall(r'server\.on\("(/api/[^"?]+)"',source))
ui_routes=set(re.findall(r"['\"](/api/[^'\"?]+)['\"]",html))
assert ui_routes<=routes, f"Missing API routes: {ui_routes-routes}"
for script in re.findall(r'<script[^>]*>(.*?)</script>',html,re.S):
    with tempfile.NamedTemporaryFile(suffix=".js") as js:
        js.write(script.encode()); js.flush(); subprocess.run(["node","--check",js.name],check=True)
parts=[]
for line in (sketch/'partitions.csv').read_text().splitlines():
    if line.strip() and not line.startswith('#'):
        name,kind,subtype,offset,size,*rest=[x.strip() for x in line.split(',')]
        parts.append((name,kind,int(offset,0),int(size,0)))
for a,b in zip(parts,parts[1:]): assert a[2]+a[3]<=b[2], 'Overlapping partitions'
assert max(x[2]+x[3] for x in parts)<=4*1024*1024
assert any(kind=='app' and size==3*1024*1024 for _,kind,_,size in parts)
assert any(name=='coredump' and size==64*1024 for name,_,_,size in parts)
for header in ('RadioCrashDumpGate.h','RadioBoundedWebServer.h','CasioBleScanControl.h','CasioModelCatalog.h','CasioStandardProtocol.h'):
    assert header in source, header
assert 'extern "C" void sntp_sync_time' in source
print(f'PASS CasioSync {version} {build}: bounded UI asset {len(compressed)} bytes, {len(elements.ids)} DOM IDs, {len(ui_routes)} routes; no LF API/code; 4 MB partitions')
