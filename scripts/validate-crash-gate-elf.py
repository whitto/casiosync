#!/usr/bin/env python3
"""Validate the linked ESP32/ESP32-C3 SDK panic path and cache-safe Off gate."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = "__wrap_esp_core_dump_write"
WRITER = "esp_core_dump_write"
FLAG = "(anonymous namespace)::crashDumpEnabled"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def active_sketch():
    versions = []
    for directory in (ROOT / "firmware").iterdir():
        match = re.fullmatch(r"CasioSync_V(\d+)_(\d+)", directory.name)
        if match and directory.is_dir():
            versions.append((tuple(map(int, match.groups())), directory.name))
    require(versions, "No active versioned sketch folder found")
    return max(versions)[1]


def elf_architecture(elf):
    data = elf.read_bytes()
    require(len(data) >= 52 and data[:6] == b"\x7fELF\x01\x01",
            "Expected a little-endian ELF32 release image")
    machine = struct.unpack_from("<H", data, 18)[0]
    require(machine in (94, 243), "Expected Xtensa ESP32 or RISC-V ESP32-C3 ELF")
    return "esp32c3" if machine == 243 else "node32s"


def tool_pair(tools_dir, architecture):
    family, prefix = ("esp-rv32", "riscv32-esp-elf") if architecture == "esp32c3" else ("esp-x32", "xtensa-esp32-elf")
    # The release targets pin the same 2601 toolchain on both architectures.
    base = tools_dir / "data/packages/esp32/tools" / family / "2601/bin"
    for directory in [base]:
        nm = directory / (prefix + "-nm")
        objdump = directory / (prefix + "-objdump")
        if nm.is_file() and objdump.is_file():
            return nm, objdump
    raise RuntimeError(f"Pinned {architecture} nm/objdump tools missing in {base}")


def run(tool, *arguments):
    return subprocess.check_output([str(tool), *map(str, arguments)], text=True)


def symbols(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([\da-fA-F]+)\s+(?:([\da-fA-F]+)\s+)?([A-Za-z])\s+(.+)", line)
        if match:
            address, size, kind, name = match.groups()
            result[name] = {"address": int(address, 16),
                            "size": int(size, 16) if size else None, "kind": kind}
    return result


def sections(text):
    result = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\s+(\S+)\s+([\da-fA-F]+)\s+([\da-fA-F]+)\s+", line)
        if match:
            name, size, start = match.groups()
            result.append((name, int(start, 16), int(start, 16) + int(size, 16)))
    return result


def section_contains(all_sections, prefix, address, size=1):
    return any(name.startswith(prefix) and start <= address and address + size <= end
               for name, start, end in all_sections)


def instructions(text):
    result = []
    for line in text.splitlines():
        match = re.match(r"\s*([\da-fA-F]+):\s+[\da-fA-F]+\s+(\S+)\s*(.*)", line)
        if match:
            address, operation, arguments = match.groups()
            result.append({"address": int(address, 16), "operation": operation,
                           "arguments": arguments})
    return result


def literal(instruction):
    if instruction["operation"] != "l32r":
        return None
    match = re.match(r"(a\d+),\s*([\da-fA-F]+).*?\(([\da-fA-F]+)\s+<", instruction["arguments"])
    return (match.group(1), int(match.group(2), 16), int(match.group(3), 16)) if match else None


def resolved_calls(code):
    registers, calls = {}, []
    for instruction in code:
        operation, arguments = instruction["operation"], instruction["arguments"]
        loaded = literal(instruction)
        if loaded:
            registers[loaded[0]] = loaded[2]
        elif operation.startswith("callx"):
            calls.append((instruction["address"], registers.get(arguments.strip())))
        elif operation.startswith("call"):
            match = re.match(r"([\da-fA-F]+)\s", arguments)
            calls.append((instruction["address"], int(match.group(1), 16) if match else None))
        elif not operation.startswith(("b", "ret", "j", "memw", "entry")):
            destination = re.match(r"(a\d+)\s*,", arguments)
            if destination:
                registers.pop(destination.group(1), None)
    return calls


def signed(value, bits):
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def riscv_register_update(instruction, registers):
    operation = instruction["operation"]
    arguments = instruction["arguments"].split("#", 1)[0].strip()
    parts = [part.strip() for part in arguments.split(",")]
    if operation in ("lui", "auipc") and len(parts) == 2:
        immediate = int(parts[1], 0)
        value = signed(immediate & 0xfffff, 20) << 12
        if operation == "auipc":
            value += instruction["address"]
        registers[parts[0]] = value & 0xffffffff
    elif operation in ("addi", "add") and len(parts) == 3:
        try:
            immediate = int(parts[2], 0)
        except ValueError:
            immediate = None
        base = registers.get(parts[1])
        registers[parts[0]] = (base + immediate) & 0xffffffff if isinstance(base, int) and immediate is not None else None
    elif operation == "mv" and len(parts) == 2:
        registers[parts[0]] = registers.get(parts[1])
    elif operation == "li" and len(parts) == 2:
        registers[parts[0]] = int(parts[1], 0) & 0xffffffff
    elif parts and not operation.startswith(("b", "j", "ret", "fence", "nop", "s")):
        # An unrecognized instruction cannot leave a previously resolved
        # destination live and make a subsequent indirect target look known.
        registers[parts[0]] = None


def riscv_target(instruction, registers):
    operation = instruction["operation"]
    arguments = instruction["arguments"].split("#", 1)[0].strip()
    if operation in ("j", "jal"):
        match = re.search(r"(?:^|,)\s*([\da-fA-F]+)\s+<", arguments)
        return int(match.group(1), 16) if match else None
    if operation in ("jr", "jalr"):
        parts = [part.strip() for part in arguments.split(",")]
        operand = parts[-1]
        indirect = re.fullmatch(r"(-?\d+)\((\w+)\)", operand)
        if indirect:
            value = registers.get(indirect.group(2))
            return ((value + int(indirect.group(1))) & ~1) if isinstance(value, int) else None
        value = registers.get(operand)
        return (value & ~1) if isinstance(value, int) else None
    return None


def resolved_riscv_calls(code):
    registers, calls = {"zero": 0}, []
    for instruction in code:
        operation = instruction["operation"]
        if operation in ("j", "jal", "jr", "jalr"):
            calls.append((instruction["address"], riscv_target(instruction, registers)))
            if operation in ("jal", "jalr"):
                for register in ("ra", "t0", "t1", "t2", "t3", "t4", "t5", "t6",
                                 "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"):
                    registers.pop(register, None)
        else:
            riscv_register_update(instruction, registers)
    return calls


def validate_riscv(elf, table, all_sections, panic, code, dump):
    gate, writer, flag = table[WRAPPER], table[WRITER], table[FLAG]
    # Pinned ESP32-C3 3.3.12 memory.ld: cache-independent SRAM aliases, not
    # merely a section whose name happens to contain "iram" or "dram".
    require(0x40380000 <= gate["address"] and gate["address"] + gate["size"] <= 0x403ce710,
            "RISC-V wrapper is outside pinned ESP32-C3 internal IRAM")
    require(0x3fc80000 <= flag["address"] and flag["address"] + 4 <= 0x3fcce710,
            "RISC-V gate flag is outside pinned ESP32-C3 internal DRAM")
    panic_calls = resolved_riscv_calls(panic)
    require(sum(target == gate["address"] for _, target in panic_calls) == 1,
            "Actual RISC-V SDK panic handler must call the wrapper exactly once")
    require(not any(target == writer["address"] for _, target in panic_calls),
            "RISC-V SDK panic handler can bypass the wrapper")
    # The pinned RISC-V optimizer uses a leaf wrapper with a tail jump to the
    # unchanged SDK writer. Unlike Xtensa, no memory-based literal pool is used.
    allowed = {"lui", "auipc", "addi", "add", "mv", "lw", "beqz", "j", "jr", "jal", "jalr", "ret", "nop"}
    require(code and all(item["operation"] in allowed for item in code),
            "RISC-V wrapper contains an unreviewed instruction/helper path")
    require(sum(item["operation"] == "ret" for item in code) == 1,
            "RISC-V leaf wrapper must have exactly one return")
    gate_calls = resolved_riscv_calls(code)
    require(len(gate_calls) == 1 and gate_calls[0][1] == writer["address"],
            "RISC-V wrapper must transfer only to the unchanged SDK writer")
    loads = [item for item in code if item["operation"] == "lw"]
    branches = [item for item in code if item["operation"] == "beqz"]
    require(len(loads) == 1 and len(branches) == 1,
            "Expected one RISC-V DRAM flag load and one Off branch")
    load = re.match(r"(\w+),\s*(-?\d+)\((\w+)\)", loads[0]["arguments"])
    branch = re.match(r"(\w+),\s*([\da-fA-F]+)\s+<", branches[0]["arguments"])
    require(load and branch and load.group(1) == branch.group(1),
            "RISC-V Off branch must test the loaded flag register")
    registers = {"zero": 0}
    for item in code:
        if item["operation"] == "lw":
            base = registers.get(load.group(3))
            require(isinstance(base, int) and ((base + int(load.group(2))) & 0xffffffff) == flag["address"],
                    "RISC-V flag load must read the verified aligned DRAM word")
            registers[load.group(1)] = "flag value"
        elif item["operation"] == "beqz":
            require(registers.get(branch.group(1)) == "flag value",
                    "RISC-V Off branch must test the actual DRAM flag value")
            break
        elif item["operation"] in ("ret", "j", "jr", "jal", "jalr"):
            raise RuntimeError("RISC-V wrapper transfers control before testing its gate")
        else:
            riscv_register_update(item, registers)
    return_address = int(branch.group(2), 16)
    target = next((item for item in code if item["address"] == return_address), None)
    require(target and target["operation"] == "ret", "RISC-V Off branch must return directly")
    require(loads[0]["address"] < branches[0]["address"] < gate_calls[0][0] < return_address,
            "RISC-V Off branch must skip the sole SDK writer transfer")
    require(all(section_contains(all_sections, ".iram", item["address"], 2) for item in code),
            "Every RISC-V wrapper instruction must lie in IRAM")
    return {"architecture": "esp32c3", "elf": str(elf.resolve()),
            "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "wrapper_address": hex(gate["address"]), "writer_address": hex(writer["address"]),
            "flag_address": hex(flag["address"]), "wrapper_size": gate["size"],
            "sdk_panic_calls_wrapper": True, "wrapper_and_literal_pool_in_iram": True,
            "riscv_address_materialization_uses_inline_immediates": True,
            "pinned_esp32c3_internal_sram_ranges": True,
            "wrapper_memory_reads_only_verified_dram_flag": True,
            "flag_is_aligned_dram_word": True, "off_returns_without_sdk_calls": True,
            "on_calls_only_real_sdk_writer": True, "physical_device_tested": False,
            "disassembly": dump}


def validate(elf, tools_dir, target="auto"):
    require(elf.is_file(), f"ELF missing: {elf}")
    architecture = elf_architecture(elf)
    require(target == "auto" or target == architecture,
            f"ELF architecture {architecture} does not match requested target {target}")
    nm, objdump = tool_pair(tools_dir, architecture)
    table = symbols(run(nm, "-nSC", elf))
    all_sections = sections(run(objdump, "-h", elf))
    for name in (WRAPPER, WRITER, FLAG, "esp_panic_handler"):
        require(name in table, f"Required linked symbol missing: {name}")
    gate, writer, flag = table[WRAPPER], table[WRITER], table[FLAG]
    require(gate["size"] and section_contains(all_sections, ".iram", gate["address"], gate["size"]),
            "Complete wrapper must be in IRAM")
    require(flag["size"] == 4 and flag["address"] % 4 == 0 and
            section_contains(all_sections, ".dram", flag["address"], 4),
            "Gate flag must be one aligned word in internal DRAM")

    dump = {name: run(objdump, "-d", elf, "--disassemble=" + name)
            for name in ("esp_panic_handler", WRAPPER)}
    panic = instructions(dump["esp_panic_handler"])
    code = instructions(dump[WRAPPER])
    if architecture == "esp32c3":
        return validate_riscv(elf, table, all_sections, panic, code, dump)
    panic_calls = resolved_calls(panic)
    require(any(target == gate["address"] for _, target in panic_calls),
            "Actual SDK panic handler does not call the wrapper")
    require(not any(target == writer["address"] for _, target in panic_calls),
            "SDK panic handler can bypass the wrapper")
    gate_calls = resolved_calls(code)
    require(len(gate_calls) == 1 and gate_calls[0][1] == writer["address"],
            "Wrapper must have exactly one call, to the unchanged SDK writer")

    # This deliberately accepts only the small, verified load/branch wrapper.
    # A compiler/toolchain change that adds helpers or control flow fails here
    # and requires a fresh review instead of silently widening the contract.
    allowed = {"entry", "mov", "mov.n", "or", "memw", "l32r", "l32i", "l32i.n",
               "beqz", "beqz.n", "call8", "callx8", "retw", "retw.n", "nop", "nop.n"}
    require(code and all(item["operation"] in allowed for item in code),
            "Wrapper contains an unreviewed instruction/helper path")
    require(code[0]["operation"] == "entry" and
            sum(item["operation"] in ("retw", "retw.n") for item in code) == 1,
            "Wrapper must have one entry and one return")
    literals = [literal(item) for item in code if item["operation"] == "l32r"]
    require(literals and all(item is not None for item in literals), "Unresolved wrapper literal")
    require(all(section_contains(all_sections, ".iram", item[1], 4) for item in literals),
            "Wrapper literal pool must be in IRAM, not cached flash")
    require(all(item[2] in (flag["address"], writer["address"]) for item in literals),
            "Wrapper reads an unreviewed literal/data address")

    loads = [item for item in code if item["operation"] in ("l32i", "l32i.n")]
    branches = [item for item in code if item["operation"] in ("beqz", "beqz.n")]
    require(len(loads) == 1 and len(branches) == 1, "Expected one flag load and one Off branch")
    load = re.fullmatch(r"(a\d+),\s*(a\d+),\s*0", loads[0]["arguments"])
    branch = re.match(r"(a\d+),\s*([\da-fA-F]+)\s", branches[0]["arguments"])
    require(load and branch and load.group(1) == branch.group(1), "Off branch must test the loaded flag")
    # Follow the actual prefix register values, so a literal/register overwrite
    # cannot turn the flag load into an access to cached flash or other data.
    registers = {}
    for item in code:
        loaded = literal(item)
        if loaded:
            registers[loaded[0]] = loaded[2]
        elif item["operation"] in ("l32i", "l32i.n"):
            require(registers.get(load.group(2)) == flag["address"],
                    "Flag load must read the verified DRAM word")
            registers[load.group(1)] = "flag value"
        elif item["operation"] in ("mov", "mov.n", "or"):
            parts = [part.strip() for part in item["arguments"].split(",")]
            registers[parts[0]] = registers.get(parts[1]) if len(parts) >= 2 else None
        elif item["operation"] in ("beqz", "beqz.n"):
            require(registers.get(branch.group(1)) == "flag value",
                    "Off branch must test the actual DRAM flag value")
            break
        elif item["operation"] in ("retw", "retw.n"):
            raise RuntimeError("Wrapper returns before checking the gate")
    return_address = int(branch.group(2), 16)
    target = next((item for item in code if item["address"] == return_address), None)
    require(target and target["operation"] in ("retw", "retw.n"), "Off branch must return directly")
    require(loads[0]["address"] < branches[0]["address"] < gate_calls[0][0] < return_address,
            "Off branch must skip the sole SDK writer call")

    return {"architecture": "node32s", "elf": str(elf.resolve()), "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "wrapper_address": hex(gate["address"]), "writer_address": hex(writer["address"]),
            "flag_address": hex(flag["address"]), "wrapper_size": gate["size"],
            "sdk_panic_calls_wrapper": True, "wrapper_and_literal_pool_in_iram": True,
            "flag_is_aligned_dram_word": True, "off_returns_without_sdk_calls": True,
            "on_calls_only_real_sdk_writer": True, "physical_device_tested": False,
            "disassembly": dump}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", nargs="?", type=Path)
    parser.add_argument("--target", choices=("auto", "node32s", "esp32c3"), default="auto")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence file")
    arguments = parser.parse_args()
    tools_dir = Path(os.environ.get("CASIOSYNC_TOOLS_DIR", os.environ.get("RADIOCLOCK_TOOLS_DIR", "/workspace/.radioclock-tools")))
    sketch = active_sketch()
    elf = arguments.elf or tools_dir / "output" / sketch / (sketch + ".ino.elf")
    try:
        report = validate(elf, tools_dir, arguments.target)
        if arguments.output:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(report, indent=2) + "\n")
        print("PASS crash dump gate: SDK panic -> IRAM wrapper; Off skips flash writer; "
              "On delegates to SDK; " + report["architecture"] + " aligned DRAM flag " + report["flag_address"])
        return 0
    except (RuntimeError, OSError, struct.error, subprocess.CalledProcessError) as error:
        print("FAIL crash dump gate: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
