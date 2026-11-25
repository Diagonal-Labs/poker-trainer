"""The committed starter charts must be exactly what the generator produces."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_generator_reproduces_committed_charts(tmp_path: Path) -> None:
    before = {p.name: p.read_text() for p in (ROOT / "data" / "charts").glob("*.json")}
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_charts.py")],
        check=True,
        capture_output=True,
        cwd=ROOT,
    )
    after = {p.name: p.read_text() for p in (ROOT / "data" / "charts").glob("*.json")}
    assert after == before, "run `make charts` and commit the regenerated files"
    assert all(json.loads(text)["schemaVersion"] == 1 for text in after.values())
