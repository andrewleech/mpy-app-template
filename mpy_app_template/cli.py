"""
Entry point for creating and updating a project from this template.

The port and board questions offer lists read from MicroPython at the moment
they are asked. Copier has no way to fetch those itself, so this command reads
them and hands them over as answer data.

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
        description="Create or update a MicroPython application project.",
    )
    parser.add_argument("destination", type=Path,
                        help="project directory to create, or update in place")
    parser.add_argument("--update", action="store_true",
                        help="re-apply the template to an existing project")
    parser.add_argument("--vcs-ref", default="main",
                        help="template ref to use (default: main)")
    parser.add_argument("--src", default=TEMPLATE_URL,
                        help="template source, for working on the template itself")
    parser.add_argument("--data-file", type=Path,
                        help="answers file, for unattended generation")
    parser.add_argument("--defaults", action="store_true",
                        help="take the default for every unanswered question")
    args = parser.parse_args(argv)

    from copier import run_copy, run_update

    from .boards import port_boards

    data: dict = {"port_boards": port_boards()}
    if args.data_file:
        import yaml

        data.update({
            key: value
            for key, value in yaml.safe_load(args.data_file.read_text()).items()
            if not key.startswith("_")
        })

    if args.update:
        run_update(args.destination, data=data, overwrite=True, unsafe=True)
        return 0

    args.destination.mkdir(parents=True, exist_ok=True)
    run_copy(
        args.src,
        args.destination,
        vcs_ref=args.vcs_ref,
        data=data,
        defaults=args.defaults or bool(args.data_file),
        unsafe=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
