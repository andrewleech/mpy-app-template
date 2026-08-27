"""
Jinja extension supplying the port and board choices to copier.

Copier renders a question's `choices` through Jinja, so a question can call
into here and offer a list that reflects MicroPython right now. The port list
comes from mpbuild, which owns the mapping from port to build container. The
board list comes from the MicroPython repository, using the same rule mpbuild
uses to discover boards: a directory under ports/<port>/boards/ holding a
board.json.

Reading the boards from the repository rather than a checkout keeps the
questions answerable before anything has been cloned, which is when copier
asks them.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from jinja2.ext import Extension

# Ports mpbuild can build that make no sense to start an application project
# from: they produce a host binary rather than firmware for a board.
EXCLUDED_PORTS = frozenset({"webassembly", "windows"})

# Ports with no board directory of their own. unix is offered because it is
# the test target and useful in its own right.
BOARDLESS_PORTS = frozenset({"unix"})

TREE_URL = (
    "https://api.github.com/repos/micropython/micropython/git/trees/{ref}?recursive=1"
)
DEFAULT_REF = "master"
TIMEOUT = 30

_board_cache: dict[str, dict[str, list[str]]] = {}


def micropython_ref() -> str:
    """Which MicroPython ref to read boards from.

    Generated projects track master, so that is the default. Override with
    MPY_BOARDS_REF to match a project that will be pinned elsewhere.
    """
    return os.environ.get("MPY_BOARDS_REF", DEFAULT_REF)


def _fetch_boards(ref: str) -> dict[str, list[str]]:
    """Every board in the MicroPython tree, keyed by port.

    One request covers all ports. The result is cached for the life of the
    process, so answering the questions costs a single round trip.
    """
    if ref in _board_cache:
        return _board_cache[ref]

    request = urllib.request.Request(
        TREE_URL.format(ref=ref),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "mpy-app-template",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            tree = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        raise RuntimeError(
            f"Could not read the MicroPython board list from GitHub ({err}). "
            "Generating a project needs network access anyway, so check the "
            "connection and try again."
        ) from err

    boards: dict[str, list[str]] = {}
    for entry in tree.get("tree", ()):
        parts = entry["path"].split("/")
        # ports/<port>/boards/<board>/board.json, the same shape mpbuild globs
        if (
            len(parts) == 5
            and parts[0] == "ports"
            and parts[2] == "boards"
            and parts[4] == "board.json"
        ):
            boards.setdefault(parts[1], []).append(parts[3])

    if tree.get("truncated"):
        raise RuntimeError(
            "GitHub truncated the MicroPython tree listing, so the board list "
            "would be incomplete."
        )

    for names in boards.values():
        names.sort()
    _board_cache[ref] = boards
    return boards


def mpbuild_ports() -> list[str]:
    """Ports mpbuild can build in a container, minus the host-binary ones."""
    from mpbuild.build import BUILD_CONTAINERS

    boards = _fetch_boards(micropython_ref())
    return sorted(
        port
        for port in set(BUILD_CONTAINERS) - EXCLUDED_PORTS
        if port in boards or port in BOARDLESS_PORTS
    )


def boards_for(port: str) -> list[str]:
    """Boards the given port offers."""
    return _fetch_boards(micropython_ref()).get(port, [])


class MicroPythonExtension(Extension):
    """Expose the port and board lookups to copier's questions."""

    def __init__(self, environment):
        super().__init__(environment)
        environment.globals["mpbuild_ports"] = mpbuild_ports
        environment.globals["boards_for"] = boards_for
