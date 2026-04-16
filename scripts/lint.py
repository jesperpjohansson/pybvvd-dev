"""
Lint codebase.

This script checks for formatting and linting rule violations in Python code
in `pybvvd/`, `tests/`, and `scripts/`.

Intended Use Cases
------------------
- Local development
- GitHub workflows

Usage
-----
python -m scripts.lint

Notes
-----
Paths and rules should be configured in `pyproject.toml` under `[tool.ruff]`.
"""

import argparse
import subprocess
import sys

from scripts._utils import check_dependencies_installed, print_func_factory

check_dependencies_installed("lint")

TASKS = {
    "format diff": [sys.executable, "-m", "ruff", "format", "--diff"],
    "lint check": [sys.executable, "-m", "ruff", "check"],
}

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--ff", action="store_true", help="fail fast")
ARGS = PARSER.parse_args()

_print = print_func_factory("lint")

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
