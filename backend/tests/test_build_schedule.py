import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_an_interrupted_write_keeps_the_old_schedule(tmp_path, monkeypatch):
    from backend.daily import schedule_code
    from backend.scripts import build_schedule as bs

    path = tmp_path / "schedule.txt"
    path.write_text(schedule_code("piano", "some-test-key") + "\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(bs, "SCHEDULE_PATH", path)
    monkeypatch.setattr(bs, "schedule_key", lambda: "some-test-key")
    monkeypatch.setattr(sys, "argv", ["build_schedule.py"])

    def stopped(fd):
        raise OSError("disk full")

    monkeypatch.setattr("os.fsync", stopped)
    with pytest.raises(OSError):
        bs.main()
    assert path.read_bytes() == before
