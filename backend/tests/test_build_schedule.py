import os
import subprocess
import sys
from pathlib import Path

from backend.daily import read_codes

ROOT = Path(__file__).resolve().parents[2]


def test_schedule_path_may_be_relative(tmp_path):
    # The README's quick start sets a relative WORDHUNT_SCHEDULE_PATH.
    env = {
        **os.environ,
        "WORDHUNT_SCHEDULE_KEY": "some-test-key",
        "WORDHUNT_SCHEDULE_PATH": "my_schedule.txt",
    }
    script = ROOT / "backend" / "scripts" / "build_schedule.py"
    done = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert read_codes(tmp_path / "my_schedule.txt")
