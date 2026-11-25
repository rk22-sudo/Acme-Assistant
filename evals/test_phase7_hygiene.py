import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KEY = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / line for line in out.splitlines() if line]


def test_env_file_is_not_tracked():
    assert ".env" not in [p.name for p in tracked_files()]


def test_no_google_api_key_in_tracked_files():
    for path in tracked_files():
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not KEY.search(text), f"API key-like string in {path.relative_to(ROOT)}"