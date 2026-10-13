#!/usr/bin/env python3
"""Production bounded classifier against independent pinned upstream model names."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = r"""
#include "CasioModelCatalog.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
using namespace CasioModelCatalog;
struct Expected {const char* name;Protocol protocol;};
static const Expected expected[] = {
    {"ABL-100", Protocol::Standard},
    {"ABL-100WE", Protocol::Standard},
    {"BSA-B100", Protocol::Standard},
    {"DW-B5600", Protocol::Standard},
    {"ECB-10", Protocol::Standard},
    {"ECB-20", Protocol::Standard},
    {"ECB-2000", Protocol::Standard},
    {"ECB-2200", Protocol::Standard},
    {"ECB-2300", Protocol::Standard},
    {"ECB-30", Protocol::Standard},
    {"ECB-40", Protocol::Standard},
    {"ECB-500", Protocol::Standard},
    {"ECB-800", Protocol::Standard},
    {"ECB-900", Protocol::Standard},
    {"ECB-950", Protocol::Standard},
    {"ECB-S10", Protocol::Standard},
    {"ECB-S100", Protocol::Standard},
    {"EQB-1000", Protocol::Standard},
    {"EQB-1100", Protocol::Standard},
    {"EQB-1200", Protocol::Standard},
    {"EQB-1300", Protocol::Standard},
    {"EQB-2000", Protocol::Standard},
    {"EQB-500", Protocol::Standard},
    {"EQB-501", Protocol::Standard},
    {"EQB-510", Protocol::Standard},
    {"EQB-600", Protocol::Standard},
    {"EQB-700", Protocol::Standard},
    {"EQB-800", Protocol::Standard},
    {"EQB-900", Protocol::Standard},
    {"F-B100W", Protocol::Standard},
    {"G-B001", Protocol::Standard},
    {"GA-B001", Protocol::Standard},
    {"GA-B010", Protocol::Standard},
    {"GA-B2100", Protocol::Standard},
    {"GBA-400", Protocol::Standard},
    {"GBA-800", Protocol::Standard},
    {"GBA-900", Protocol::Standard},
    {"GBA-950", Protocol::Standard},
    {"GBD-800", Protocol::Standard},
    {"GBM-2100", Protocol::Standard},
    {"GCW-B5000", Protocol::Standard},
    {"GD-B500", Protocol::Standard},
    {"GG-B100", Protocol::Standard},
    {"GG-B100X", Protocol::Standard},
    {"GM-B2100", Protocol::Standard},
    {"GMA-B800", Protocol::Standard},
    {"GMC-B100", Protocol::Standard},
    {"GMC-B2100", Protocol::Standard},
    {"GMD-B300", Protocol::Standard},
    {"GMD-B800", Protocol::Standard},
    {"GMW-B5000", Protocol::Standard},
    {"GMW-B5000#", Protocol::Standard},
    {"GMW-BZ5000", Protocol::Standard},
    {"GPR-B1000", Protocol::Standard},
    {"GPW-2000", Protocol::Standard},
    {"GPW-G2000", Protocol::Standard},
    {"GR-B100", Protocol::Standard},
    {"GR-B200", Protocol::Standard},
    {"GR-B300", Protocol::Standard},
    {"GST-B100", Protocol::Standard},
    {"GST-B1000", Protocol::Standard},
    {"GST-B200", Protocol::Standard},
    {"GST-B300", Protocol::Standard},
    {"GST-B400", Protocol::Standard},
    {"GST-B500", Protocol::Standard},
    {"GST-B600", Protocol::Standard},
    {"GST-W1000", Protocol::Standard},
    {"GW-B5000", Protocol::Standard},
    {"GW-B5600", Protocol::Standard},
    {"GW-B5600#", Protocol::Standard},
    {"GW-BX5600", Protocol::Bx5600},
    {"GWF-300", Protocol::Standard},
    {"GWF-A1000", Protocol::Standard},
    {"GWG-B1000", Protocol::Standard},
    {"GWR-B1000", Protocol::Standard},
    {"GWR-B3000", Protocol::Standard},
    {"LIW-B1000", Protocol::Standard},
    {"MRG-B1000", Protocol::Standard},
    {"MRG-B2000", Protocol::Standard},
    {"MRG-B2100", Protocol::Standard},
    {"MRG-B5000", Protocol::Standard},
    {"MRG-B5000#", Protocol::Standard},
    {"MRG-BF1000", Protocol::Standard},
    {"MRG-G2000", Protocol::Standard},
    {"MSG-B100", Protocol::Standard},
    {"MTG-B1000", Protocol::Analogue},
    {"MTG-B2000", Protocol::Standard},
    {"MTG-B3000", Protocol::Analogue},
    {"MTG-B3100", Protocol::Analogue},
    {"MTG-B4000", Protocol::Standard},
    {"OCW-5700", Protocol::Standard},
    {"OCW-5800", Protocol::Standard},
    {"OCW-B1200", Protocol::Standard},
    {"OCW-B1300", Protocol::Standard},
    {"OCW-B1400", Protocol::Standard},
    {"OCW-G2000", Protocol::Standard},
    {"OCW-P2000", Protocol::Standard},
    {"OCW-P3000", Protocol::Standard},
    {"OCW-S400", Protocol::Standard},
    {"OCW-S4000", Protocol::Standard},
    {"OCW-S5000", Protocol::Standard},
    {"OCW-S6000", Protocol::Standard},
    {"OCW-S7000", Protocol::Standard},
    {"OCW-SG1000", Protocol::Standard},
    {"OCW-T200", Protocol::Standard},
    {"OCW-T3000", Protocol::Standard},
    {"OCW-T4000", Protocol::Standard},
    {"OCW-T4000A", Protocol::Standard},
    {"OCW-T4000B", Protocol::Standard},
    {"OCW-T4000C", Protocol::Standard},
    {"OCW-T5000", Protocol::Standard},
    {"OCW-T6000", Protocol::Standard},
    {"PRJ-B001", Protocol::Standard},
    {"PRJ-BW002", Protocol::Standard},
    {"PRT-B50", Protocol::Standard},
    {"PRT-B70", Protocol::Standard},
    {"PRW-B1000", Protocol::Standard},
    {"SHB-100", Protocol::Standard},
    {"SHB-200", Protocol::Standard},
    {"STB-1000", Protocol::Standard},
    {"TRN-50", Protocol::Standard},
    {"WS-B1000", Protocol::Standard},
};
static void unknown(const char *name,size_t length) {
  const auto value=classify(name,length);
  assert(value.model==nullptr && value.protocol==Protocol::Unknown && !value.automatic);
  for(auto protocol:{Protocol::Bx5600,Protocol::Standard,Protocol::Analogue,Protocol::Unknown})
    assert(!matches(protocol,name,length));
}
int main() {
  static_assert(ModelCount==122,"Pinned catalog has 122 candidates");
  for(const auto& entry:expected) {
    const auto plain=classify(entry.name,std::strlen(entry.name));
    assert(plain.automatic && plain.protocol==entry.protocol && std::strcmp(plain.model,entry.name)==0);
    std::string lower=" \tcasio  ";
    for(const char *ch=entry.name;*ch;++ch) lower += (*ch>='A' && *ch<='Z') ? char(*ch+32) : *ch;
    lower += "\t ";
    assert(matches(entry.protocol,lower.data(),lower.size()));
    for(auto protocol:{Protocol::Bx5600,Protocol::Standard,Protocol::Analogue})
      if(protocol!=entry.protocol) assert(!matches(protocol,entry.name,std::strlen(entry.name)));
    const auto badPrefix=std::string("OTHER-")+entry.name;
    unknown(badPrefix.data(),badPrefix.size());
    const auto badSuffix=std::string(entry.name)+"-1A";
    unknown(badSuffix.data(),badSuffix.size());
  }
  unknown(nullptr,0); unknown(nullptr,12); unknown("",0);
  for(const auto* name:{"GW-BX5600X","GW-BX56000","GW-B56000","GW-BX5600 fake","FAKE CASIO GW-BX5600",
      "CASIO GW-BX5600\n","CASIO GPR-H1000","CASIO DW-H5600","CASIO GBD-200","CASIO GB-5600A","CASIO GW-BX9999"})
    unknown(name,std::strlen(name));
  const char rawNoNul[8]={'G','W','-','B','5','6','0','0'};
  assert(matches(Protocol::Standard,rawNoNul,sizeof(rawNoNul)));
  const char embeddedNul[12]={'G','W','-','B','X','5','6','0','0','\0','A','A'};
  unknown(embeddedNul,sizeof(embeddedNul));
  const char longName[65]={}; unknown(longName,sizeof(longName));
  unknown(rawNoNul,size_t(-1)); // Reject length before accessing any bytes.
  uint32_t seed=0x4d424c45;
  for(unsigned pass=0;pass<100000;++pass) {
    char bytes[64];
    for(char& byte:bytes) {seed=seed*1664525u+1013904223u;byte=char(seed>>24);}
    const auto result=classify(bytes,pass%65);
    assert(result.protocol==Protocol::Unknown || result.model!=nullptr);
  }
  std::cout << "Catalog: 122 pinned entries, exact protocol boundaries, malformed lengths and 100000 bounded fuzz names passed\n";
}
"""

class CatalogTests(unittest.TestCase):
    def test_exact_catalog_and_bounded_advertisements(self):
        with tempfile.TemporaryDirectory(prefix="casiosync-catalog-") as temp:
            fixture = Path(temp) / "catalog.cpp"
            binary = Path(temp) / "catalog"
            fixture.write_text(SOURCE)
            subprocess.run(["g++", "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie",
                            "-I", str(ROOT / "firmware/CasioSync_V0_1"), str(fixture),
                            "-o", str(binary)], check=True)
            env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1")
            result = subprocess.run([str(binary)], text=True, capture_output=True, env=env, check=True)
            self.assertIn("122 pinned entries", result.stdout)
            print(result.stdout.strip())

if __name__ == "__main__":
    unittest.main()
