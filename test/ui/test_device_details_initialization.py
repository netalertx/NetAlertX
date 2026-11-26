"""Run the source-level device-details initialization regression."""

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NODE_TEST = Path(__file__).with_suffix(".cjs")


def test_device_details_initialization_regression():
    """Exercise real inline JavaScript branches through the Node VM harness."""
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the device-details source regression"

    result = subprocess.run(
        [node, str(NODE_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"Node regression failed:\n{result.stdout}\n{result.stderr}"
