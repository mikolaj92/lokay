"""Repair receipt file locks serialize updates across processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from lokay.proc import pr_repair_receipts


def test_process_concurrent_updates_preserve_every_attempt(tmp_path):
    workers = 6
    updates = 7
    code = '''
import sys
from lokay.proc.pr_repair_receipts import stamp
state = sys.argv[1]
workers, updates = int(sys.argv[2]), int(sys.argv[3])
for _ in range(updates):
    stamp("o/r", 9, state_dir=state, budget=workers * updates, terminal="legacy-confirmed")
'''
    env = os.environ.copy()
    src = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path), str(workers), str(updates)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(workers)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, (stdout, stderr)

    stored = pr_repair_receipts.read("o/r", 9, state_dir=tmp_path)
    assert stored["attempts"] == workers * updates
