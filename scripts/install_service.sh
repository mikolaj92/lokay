#!/usr/bin/env bash
set -euo pipefail
ROOT="${LOKAY_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS"
python3 - "$ROOT" "$AGENTS" <<'PY'
import copy
import plistlib
import sys
from pathlib import Path

root, agents = map(Path, sys.argv[1:])
with (root / "scripts/ai.mikolaj.lokay2.plist").open("rb") as stream:
    service = plistlib.load(stream)
service["ProgramArguments"][1] = str(root / "scripts/lokay-service.sh")
monitor = copy.deepcopy(service)
monitor["Label"] += ".monitor"
monitor["ProgramArguments"].append("--monitor")
monitor.pop("KeepAlive")
monitor["StartInterval"] = 60
for config in (service, monitor):
    with (agents / (config["Label"] + ".plist")).open("wb") as stream:
        plistlib.dump(config, stream)
PY
domain="gui/$(id -u)"
# Retire the old label to avoid two factories running together.
launchctl bootout "$domain/ai.mikolaj.lokay" 2>/dev/null || true
for label in ai.mikolaj.lokay2 ai.mikolaj.lokay2.monitor; do
  launchctl bootout "$domain/$label" 2>/dev/null || true
  launchctl bootstrap "$domain" "$AGENTS/$label.plist"
done
