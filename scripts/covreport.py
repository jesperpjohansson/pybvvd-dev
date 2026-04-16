"""
Produce a coverage report.

This script silently runs the test suite and writes a coverage report to
the project root directory.

Intended Use Cases
------------------
- Local development
- GitHub workflows

Positional Arguments
--------------------
type : {"term-missing", "json", "xml", "html"}
    Coverage report type.

Usage
-----
python -m scripts.update_coverage_badge TYPE

Notes
-----
If the selected report type is `json`, the output file is reformatted with indentation
for improved readability.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from scripts._utils import check_dependencies_installed, print_func_factory

_print = print_func_factory("covreport")

REPORT_TYPES = ["term-missing", "json", "xml", "html"]
REPORT_PATHS = [".coverage", "coverage.json", "coverage.xml", "htmlcov"]
REPORT_TYPE_TO_PATH = dict(zip(REPORT_TYPES, REPORT_PATHS, strict=False))

parser = argparse.ArgumentParser()
parser.add_argument("type", choices=REPORT_TYPES, help="report type")
args = parser.parse_args()

check_dependencies_installed("covreport")

_print(f"running tests and saving {args.type} report")

code = subprocess.run(
    ["pytest", "--cov=pybvvd", f"--cov-report={args.type}"],
    check=False,
    capture_output=True,
).returncode

if code > 0:
    sys.exit(code)

path = Path(__file__).parents[1] / REPORT_TYPE_TO_PATH[args.type]

# Indentation is added to json reports to increase readability
if args.type == "json":
    with path.open("r", encoding="utf-8") as stream:
        covreport = json.load(stream)

    with path.open("w", encoding="utf-8") as stream:
        json.dump(covreport, stream, ensure_ascii=False, indent=4)

_print(f"report saved: {path}")
