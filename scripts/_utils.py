"""Internal utilities."""

from collections.abc import Callable, Iterator
from functools import partial
import importlib.util
from pathlib import Path
import re
import sys

# Names of scripts that requires pybvvd
REQUIRES_PYBVVD = frozenset(("covreport", "test"))

# Mapping of script name to requirements file name
REQUIREMENTS_FILE = {
    "covreport": "covreport.txt",
    "format": "lint.txt",
    "lint": "lint.txt",
    "test": "test.txt",
    "typecheck": "typecheck.txt",
}

# Absolute path to the requirements directory
REQUIREMENTS_DIR = Path(__file__).parents[1] / "requirements"

# Regular expression used when parsing requirements/*.txt files
DEPENDENCY_RE = re.compile(
    r"([\w\.-]+)"  # Distribution name
    r".+#\s*import:\s*"
    r"([\w\.-]+)"  # Import name
)

REFERENCE_RE = re.compile(r"-r ([^\s]+)")


def _get_requirements(filename: str) -> tuple[tuple[str, str], ...]:
    """
    Extract and map aliases of all dependencies listed in requirements/`filename`.

    This function reads and parses a `.txt` file listing script dependencies. Each
    specified distribution name is assumed to be followed by a comment starting with
    `import:`, followed by the import name of the corresponding distribution,
    for example: `my-package # import: my_package`.
    """

    def get_match_groups(m: re.Match[str]) -> Iterator[str]:
        for value in m.groups():
            if isinstance(value, str):
                yield value
            else:
                exc_msg = "Match group contains non-str value."
                raise TypeError(exc_msg)

    def parse_lines(stream: Iterator[str]) -> Iterator[tuple[str, str]]:
        for line in stream:
            if m := REFERENCE_RE.match(line):
                reference_name, *_ = get_match_groups(m)

                yield from _get_requirements(reference_name)
            elif m := DEPENDENCY_RE.match(line):
                distribution_name, import_name = get_match_groups(m)

                yield distribution_name, import_name

    with (REQUIREMENTS_DIR / filename).open("r", encoding="utf-8") as stream:
        return tuple(parse_lines(stream))


def check_dependencies_installed(script_name: str) -> None:
    """Exit with code 1 if not all required dependencies are installed."""
    requirements = dict(_get_requirements(REQUIREMENTS_FILE[script_name]))

    if script_name in REQUIRES_PYBVVD:
        requirements["pybvvd"] = "pybvvd"

    missing = tuple(
        distribution_name
        for distribution_name, import_name in requirements.items()
        if not importlib.util.find_spec(import_name)
    )
    if missing:
        print(
            f"[scripts.{script_name}] missing requirements: {', '.join(missing)}"
            f"\ninstall: python -m pip install -e .[dev]",
            flush=True,
        )
        sys.exit(1)


def print_func_factory(script_name: str) -> Callable[..., None]:
    return partial(print, f"[scripts.{script_name}]", flush=True)
