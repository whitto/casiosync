#!/usr/bin/env python3
"""Verify actual SDK dispatch to the strong SNTP pre-commit hook.

Xtensa SDK text sometimes has data mapping metadata, so read ELF LOAD bytes
and decode CALL8 directly. For ESP32-C3, decode real RV32IMC JAL/C.JAL and
AUIPC/JALR dispatch targets from those same LOAD bytes. No physical claim.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def load_symbol_bytes(data, address, size):
    phoff = struct.unpack_from('<I', data, 28)[0]
    entry_size, entries = struct.unpack_from('<HH', data, 42)
    require(entry_size >= 32, 'ELF32 program headers are too short')
    require(phoff + entry_size * entries <= len(data), 'ELF32 program headers exceed file bounds')
    for index in range(entries):
        kind, offset, start, _, file_size, _, _, _ = struct.unpack_from('<IIIIIIII', data, phoff + index * entry_size)
        if kind == 1 and start <= address and address + size <= start + file_size:
            begin = offset + address - start
            require(begin + size <= len(data), 'Symbol LOAD bytes exceed file bounds')
            return data[begin:begin + size]
    raise RuntimeError('SDK SNTP dispatch bytes missing from LOAD segments')


def xtensa_dispatches(raw, caller, hook):
    calls = []
    # Retain the established pinned Xtensa mapping-independent CALL8 check.
    for offset in range(len(raw) - 2):
        instruction = int.from_bytes(raw[offset:offset + 3], 'little')
        if instruction & 0x3f != 0x25:
            continue
        displacement = signed(instruction >> 6, 18)
        target = ((caller + offset + 4) & ~3) + (displacement << 2)
        if target == hook:
            calls.append(caller + offset)
    return calls


def compressed_jump_immediate(instruction):
    value = (((instruction >> 12) & 1) << 11 | ((instruction >> 11) & 1) << 4 |
             ((instruction >> 9) & 3) << 8 | ((instruction >> 8) & 1) << 10 |
             ((instruction >> 7) & 1) << 6 | ((instruction >> 6) & 1) << 7 |
             ((instruction >> 3) & 7) << 1 | ((instruction >> 2) & 1) << 5)
    return signed(value, 12)


def riscv_dispatches(raw, caller, hook):
    calls, registers, offset = [], {0: 0}, 0
    while offset < len(raw):
        require(offset + 2 <= len(raw), 'Truncated RISC-V instruction')
        low = int.from_bytes(raw[offset:offset + 2], 'little')
        address = caller + offset
        if low & 3 != 3:
            quadrant, function = low & 3, low >> 13
            if quadrant == 1 and function in (1, 5):  # RV32 C.JAL / C.J tail dispatch.
                if address + compressed_jump_immediate(low) == hook:
                    calls.append(address)
                registers = {0: 0}
            elif quadrant == 2 and function == 4 and ((low >> 2) & 31) == 0:
                source = (low >> 7) & 31  # C.JR or C.JALR; RET resolves to unknown RA.
                value = registers.get(source)
                if isinstance(value, int) and value & ~1 == hook:
                    calls.append(address)
                registers = {0: 0}
            elif not ((quadrant == 0 and function in (6, 7)) or
                      (quadrant == 2 and function in (6, 7)) or
                      (quadrant == 1 and function in (6, 7))):
                # Other compressed writes cannot retain a stale resolved
                # address. AUIPC/JALR compiler call pairs are consecutive.
                registers = {0: 0}
            offset += 2
            continue
        require((low >> 2) & 7 != 7, 'Unreviewed extended RISC-V instruction encoding')
        require(offset + 4 <= len(raw), 'Truncated RISC-V 32-bit instruction')
        instruction = int.from_bytes(raw[offset:offset + 4], 'little')
        opcode, destination = instruction & 0x7f, (instruction >> 7) & 31
        source = (instruction >> 15) & 31
        if opcode == 0x6f:  # JAL, including a linker-relaxed tail J with rd=zero.
            immediate = (((instruction >> 31) & 1) << 20 | ((instruction >> 21) & 0x3ff) << 1 |
                         ((instruction >> 20) & 1) << 11 | ((instruction >> 12) & 0xff) << 12)
            if address + signed(immediate, 21) == hook:
                calls.append(address)
            registers = {0: 0}
        elif opcode == 0x67 and (instruction >> 12) & 7 == 0:  # JALR.
            base = registers.get(source)
            if isinstance(base, int):
                target = (base + signed(instruction >> 20, 12)) & 0xfffffffe
                if target == hook:
                    calls.append(address)
            registers = {0: 0}
        elif opcode in (0x17, 0x37):  # AUIPC or LUI.
            value = signed(instruction & 0xfffff000, 32)
            registers[destination] = ((address if opcode == 0x17 else 0) + value) & 0xffffffff
        elif opcode == 0x13 and (instruction >> 12) & 7 == 0:  # ADDI.
            base = registers.get(source)
            registers[destination] = (base + signed(instruction >> 20, 12)) & 0xffffffff if isinstance(base, int) else None
        elif opcode not in (0x23, 0x63, 0x0f):  # Stores, branches and fence do not write rd.
            registers[destination] = None
        registers[0] = 0
        offset += 4
    return calls


def validate(elf, tools_dir, target='auto'):
    data = elf.read_bytes()
    require(len(data) >= 52 and data[:6] == b'\x7fELF\x01\x01',
            'Expected little-endian ELF32 release image')
    machine = struct.unpack_from('<H', data, 18)[0]
    require(machine in (94, 243), 'Expected Xtensa ESP32 or RISC-V ESP32-C3 ELF')
    architecture = 'esp32c3' if machine == 243 else 'node32s'
    require(target == 'auto' or target == architecture,
            f'ELF architecture {architecture} does not match requested target {target}')
    family, prefix = ('esp-rv32', 'riscv32-esp-elf') if machine == 243 else ('esp-x32', 'xtensa-esp32-elf')
    base = tools_dir / 'data/packages/esp32/tools' / family / '2601/bin'
    nm = subprocess.check_output([str(base / (prefix + '-nm')), '-S', str(elf)], text=True)

    def symbol(name):
        match = re.search(r'^([0-9a-f]+)\s+([0-9a-f]+)\s+T\s+' + re.escape(name) + r'$', nm, re.M)
        require(match, 'Missing expected strong T symbol ' + name)
        address, size = int(match[1], 16), int(match[2], 16)
        require(size > 0, 'Expected a nonempty linked function ' + name)
        return address, size

    hook, _ = symbol('sntp_sync_time')
    caller, size = symbol('sntp_set_system_time')
    raw = load_symbol_bytes(data, caller, size)
    calls = (riscv_dispatches if machine == 243 else xtensa_dispatches)(raw, caller, hook)
    require(len(calls) == 1, 'SDK SNTP dispatcher must contain exactly one dispatch to the strong pre-commit hook')
    return {'architecture': architecture, 'elf': str(elf.resolve()),
            'elf_sha256': hashlib.sha256(data).hexdigest(), 'strong_hook_address': hex(hook),
            'sdk_caller_address': hex(caller), 'dispatch_address': hex(calls[0]),
            'dispatch_decoder': 'RV32IMC instruction boundaries' if machine == 243 else 'Xtensa CALL8 raw LOAD bytes',
            'strong_sntp_precommit_dispatch': True, 'physical_device_tested': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('--target', choices=('auto', 'node32s', 'esp32c3'), default='auto')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    tools_dir = Path(os.environ.get('CASIOSYNC_TOOLS_DIR', os.environ.get('RADIOCLOCK_TOOLS_DIR', '/workspace/.radioclock-tools')))
    try:
        report = validate(args.elf, tools_dir, args.target)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(f"PASS: {report['architecture']} strong sntp_sync_time at {report['strong_hook_address']}; "
              f"SDK dispatch at {report['dispatch_address']} reaches the pre-commit gate")
        return 0
    except (RuntimeError, OSError, struct.error, subprocess.CalledProcessError) as error:
        print('FAIL SNTP dispatch: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
