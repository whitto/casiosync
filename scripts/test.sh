#!/usr/bin/env bash
# Full suite: publish the reviewed source revision before running this script.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
python3 scripts/validate-project.py
python3 tests/test_nimble_pin.py
python3 tests/test_ble_scan_control.py
python3 tests/test_crash_dump_gate.py
python3 tests/test_http_bounds.py
python3 tests/test_json_writer.py
python3 tests/test_bt_history.py
python3 tests/test_storage_policy.py
python3 tests/test_watch_options_storage.py
python3 tests/test_runtime_helpers.py
python3 tests/test_bluetooth_schedule.py
python3 tests/test_wifi_clock_policy.py
python3 tests/test_watch_battery.py
python3 tests/test_watch_feature_transport.py
python3 tests/test_model_catalog.py
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT
for fixture in bx-protocol standard-protocol watch-features; do
  source_file="tests/test_${fixture//-/_}.cpp"
  g++ -std=c++17 -O1 -Wall -Wextra -Werror -fsanitize=address,undefined \
    -fno-omit-frame-pointer -no-pie "$source_file" -o "$test_dir/$fixture"
  ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
    "$test_dir/$fixture"
done
node scripts/test-ui-browser.cjs
