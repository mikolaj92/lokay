#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
home=$(mktemp -d)
export HOME="$home"
uv run python - <<'PY'
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
from lokay.lock import acquire, release

first = acquire("mikolaj92", "mikolaj92/lokay-sandbox")
assert first["result"] == "held", first
kid_out = Path("/tmp/lokay-lock-kid")
pid = os.fork()
if pid == 0:
    second = acquire("mikolaj92", "mikolaj92/lokay-sandbox")
    kid_out.write_text(second["result"])
    os._exit(0)
os.waitpid(pid, 0)
assert kid_out.read_text() == "busy", kid_out.read_text()
other = acquire("mikolaj92", "mikolaj92/other")
assert other["result"] == "held", other
release(other)
release(first)
time.sleep(0.05)
third = acquire("mikolaj92", "mikolaj92/lokay-sandbox")
assert third["result"] == "held", third
release(third)
print("busy")
print("lock free")
PY
# death drops the lock
uv run python - <<'PY'
import os, subprocess, sys, textwrap, time
from pathlib import Path
code = textwrap.dedent("""
import os, time
from lokay.lock import acquire
held = acquire("mikolaj92", "mikolaj92/lokay-sandbox")
assert held["result"] == "held"
print(held["fd"], flush=True)
time.sleep(30)
""")
proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
line = proc.stdout.readline()
assert line.strip().isdigit(), line
proc.kill()
proc.wait(timeout=5)
from lokay.lock import acquire
again = acquire("mikolaj92", "mikolaj92/lokay-sandbox")
assert again["result"] == "held", again
print("reacquire ok")
PY
rm -rf "$home"
