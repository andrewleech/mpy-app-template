"""
Entry point for generating a project from this template.

Copier loads Jinja extensions from its own environment, so the extension that
supplies the live port and board lists has to be installed alongside it. Going
through this command means both arrive together:

    uvx --from git+https://github.com/andrewleech/mpy-app-template mpy-new my_project
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE_URL = "git+https://github.com/andrewleech/mpy-app-template"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mpy-new",
        description="Create a MicroPython application project.",
    )
    parser.add_argument("destination", type=Path, help="directory to create the project in")
    parser.add_argument("--vcs-ref", default="main", help="template ref to use (default: main)")
    parser.add_argument("--src", default=TEMPLATE_URL,
                        help="template source, for working on the template itself")
    parser.add_argument("--data-file", type=Path,
                        help="answers file, for unattended generation")
    parser.add_argument("--defaults", action="store_true",
                        help="take the default for every unanswered question")
    args = parser.parse_args(argv)

    from copier import run_copy

    data = {}
    if args.data_file:
        import yaml

        data = {
            key: value
            for key, value in yaml.safe_load(args.data_file.read_text()).items()
            if not key.startswith("_")
        }

    args.destination.mkdir(parents=True, exist_ok=True)
    run_copy(
        args.src,
        args.destination,
        vcs_ref=args.vcs_ref,
        data=data,
        defaults=args.defaults or bool(data),
        unsafe=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
