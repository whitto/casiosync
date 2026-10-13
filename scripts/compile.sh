#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
tools_dir="${RADIOCLOCK_TOOLS_DIR:-/workspace/.radioclock-tools}"
export ARDUINO_DIRECTORIES_DATA="$tools_dir/data"
export ARDUINO_DIRECTORIES_DOWNLOADS="$tools_dir/downloads"
export ARDUINO_DIRECTORIES_USER="$tools_dir/user"
export ARDUINO_BUILD_CACHE_PATH="$tools_dir/cache"
if [[ -z "${ARDUINO_NETWORK_PROXY:-}" && -n "${HTTPS_PROXY:-${https_proxy:-}}" ]]; then
  export ARDUINO_NETWORK_PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
fi
cli="$tools_dir/bin/arduino-cli"
if [[ ! -x "$cli" ]]; then
  printf '%s\n' 'Run scripts/install-toolchain.sh before compiling.' >&2
  exit 1
fi

# Both images use the supplied 4 MB / 3 MB app partition layout.
board="${CASIOSYNC_BOARD:-node32s}"
case "$board" in
  node32s) board_fqbn="esp32:esp32:node32s:FlashFreq=40,PartitionScheme=no_ota,EraseFlash=none" ;;
  esp32c3) board_fqbn="esp32:esp32:esp32c3:FlashSize=4M,FlashMode=dio,FlashFreq=40,PartitionScheme=huge_app,CDCOnBoot=cdc,EraseFlash=none" ;;
  *) printf '%s\n' 'CASIOSYNC_BOARD must be node32s or esp32c3.' >&2; exit 1 ;;
esac
fqbn="${CASIOSYNC_FQBN:-$board_fqbn}"
jobs="${CASIOSYNC_BUILD_JOBS:-2}"
extra_flags=()
if [[ "$board" == esp32c3 ]]; then
  extra_flags=(--build-property "compiler.cpp.extra_flags=-DCASIOSYNC_C3_SUPERMINI=1")
fi
sketch="$repo_dir/firmware/CasioSync_V0_1"
build_dir="$tools_dir/build/CasioSync_V0_1/$board"
output_dir="$tools_dir/output/CasioSync_V0_1/$board"
mkdir -p "$build_dir" "$output_dir"
bash "$repo_dir/scripts/install-local-library.sh"

"$cli" compile --fqbn "$fqbn" --jobs "$jobs" \
  --build-path "$build_dir" --output-dir "$output_dir" "${extra_flags[@]}" "$sketch" "$@"
python3 "$repo_dir/scripts/validate-crash-gate-elf.py" "$output_dir/CasioSync_V0_1.ino.elf"
python3 "$repo_dir/scripts/validate-reliability-elf.py" "$output_dir/CasioSync_V0_1.ino.elf"
