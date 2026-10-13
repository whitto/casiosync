"""Extract production C++ blocks and supply small host-only Arduino fixtures."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / 'firmware/CasioSync_V0_1/CasioSync_V0_1.ino'


def balanced_block(source, start):
    begin = source.index('{', start)
    depth, pos, state = 1, begin + 1, 'code'
    while depth:
        if pos >= len(source):
            raise AssertionError('Unterminated C++ block')
        char, pair = source[pos], source[pos:pos+2]
        if state == 'line':
            if char == '\n': state = 'code'
        elif state == 'block':
            if pair == '*/': state = 'code'; pos += 1
        elif state in ('"', "'"):
            if char == '\\': pos += 1
            elif char == state: state = 'code'
        elif pair == '//': state = 'line'; pos += 1
        elif pair == '/*': state = 'block'; pos += 1
        elif char in ('"', "'"): state = char
        elif char == '{': depth += 1
        elif char == '}': depth -= 1
        pos += 1
    return source[start:pos]


def extract_function(source, name):
    match = re.search(r'^(?:static )?(?:inline )?(?:bool|void|int|uint32_t|uint64_t|double|size_t|String|time_t|const char\s*\*)\s*' + re.escape(name) +
                      r'\([^;]*?\)\s*\{', source, re.M)
    if not match: raise AssertionError(f'Function {name} missing')
    return balanced_block(source, match.start())


def transaction_deadline_source(source):
    declarations = []
    for name in ('btTransactionActive', 'btTransactionStartedMillis', 'BT_TRANSACTION_DEADLINE_MS'):
        match = re.search(r'^static [^\n]*\b' + name + r'[^\n]*;', source, re.M)
        if not match: raise AssertionError(f'Deadline declaration {name} missing')
        declarations.append(match.group())
    return '\n'.join(declarations + [extract_function(source, n) for n in
                                    ('btTransactionDeadlineReached', 'btTransactionCancelled')]) + '\n'


def run_cpp(code, *, sanitized=True, timeout=30, arguments=()):
    with tempfile.TemporaryDirectory(prefix='casiosync-host-') as tmp:
        unit, binary = Path(tmp)/'test.cpp', Path(tmp)/'test'
        unit.write_text(code)
        cmd = ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
               '-I', str(FIRMWARE.parent), str(unit), '-o', str(binary)]
        if sanitized: cmd[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie']
        subprocess.run(cmd, check=True)
        env = os.environ.copy()
        env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
        env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
        return subprocess.run([str(binary), *arguments], check=True, text=True,
                              capture_output=True, timeout=timeout, env=env)


MOCKS = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <strings.h>
size_t strlcpy(char* to, const char* from, size_t count) {
  if (count) { std::strncpy(to, from, count - 1); to[count - 1] = '\0'; }
  return std::strlen(from);
}
class String {
public:
  std::string s;
  String(const char* p = "") : s(p) {}
  String(std::string p) : s(std::move(p)) {}
  String(int n) : s(std::to_string(n)) {}
  String(unsigned long n) : s(std::to_string(n)) {}
  size_t length() const { return s.length(); }
  const char* c_str() const { return s.c_str(); }
  bool reserve(size_t n) { s.reserve(n); return true; }
  void trim() {
    auto first = s.find_first_not_of(" \t\r\n");
    s = first == std::string::npos ? "" : s.substr(first, s.find_last_not_of(" \t\r\n") - first + 1);
  }
  void replace(const char* from, const char* to) {
    size_t pos = 0;
    while ((pos = s.find(from, pos)) != std::string::npos) {
      s.replace(pos, std::strlen(from), to); pos += std::strlen(to);
    }
  }
  void toUpperCase() { for (auto& c : s) c = std::toupper(static_cast<unsigned char>(c)); }
  int indexOf(const char* p) const { auto pos = s.find(p); return pos == std::string::npos ? -1 : int(pos); }
  bool equalsIgnoreCase(const char* p) const { return strcasecmp(s.c_str(), p) == 0; }
  long toInt() const { return std::strtol(s.c_str(), nullptr, 10); }
  void toCharArray(char* out, size_t count) const { strlcpy(out, c_str(), count); }
  String& operator+=(const String& v) { s += v.s; return *this; }
  String& operator+=(char v) { s += v; return *this; }
  friend String operator+(const String& a, const String& b) { return String(a.s + b.s); }
  friend bool operator==(const String& a, const String& b) { return a.s == b.s; }
  friend bool operator!=(const String& a, const String& b) { return !(a == b); }
};
'''
