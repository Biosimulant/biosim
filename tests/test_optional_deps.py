import os
import subprocess
import sys
from pathlib import Path


def test_import_bsim_does_not_import_fastapi_in_fresh_process():
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    code = "import sys; import biosim; print('fastapi' in sys.modules)"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "False"
