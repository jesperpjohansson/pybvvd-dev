"""
Format codebase.

This script applies in-place formatting and safe lint fixes to Python code in
`pybvvd/`, `tests/`, and `scripts/`.

Intended Use Cases
------------------
- Local development

Optional Arguments
------------------
--ff : store_true
    Stop execution after the first failed task (fail fast).

Usage
-----
python -m scripts.format --ff
"""

import argparse
import subprocess
import sys

from scripts._utils import check_dependencies_installed, print_func_factory

check_dependencies_installed("format")


TASKS = {
    "format": [sys.executable, "-m", "ruff", "format"],
    "lint fix": [sys.executable, "-m", "ruff", "check", "--fix-only"],
}

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--ff", action="store_true", help="fail fast")
ARGS = PARSER.parse_args()

_print = print_func_factory("format")

failed = False
for task, cmd in TASKS.items():
    code = subprocess.run(cmd, check=False).returncode
    status = "OK" if code == 0 else "FAIL"
    _print(f"{task} | code {code} | status {status}")

    if status == "FAIL" and not failed:
        failed = True
        if ARGS.ff:
            break


sys.exit(int(failed))
