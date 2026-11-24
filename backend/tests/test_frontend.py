"""Runs frontend.test.mjs, the tests of docs/js, with Node (skipped without it)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.config import BASE_DIR


def test_frontend(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node isn't installed")
    # A copy, with a package.json that tells Node these are ES modules.
    shutil.copytree(BASE_DIR / "docs" / "js", tmp_path / "js")
    (tmp_path / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    done = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("frontend.test.mjs"))],
        env={**os.environ, "JS_DIR": str(tmp_path / "js")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
