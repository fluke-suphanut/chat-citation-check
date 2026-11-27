import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_demo_runs_and_removes_the_three_bad_citations():
    out = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "demo.py")],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(ROOT / "src")},
    ).stdout
    assert "kept 3, removed 3" in out
    assert "the assistant never read this document" in out
