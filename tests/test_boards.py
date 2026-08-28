"""Tests for the port and board lookups."""

import json
import urllib.error
from io import BytesIO

import pytest

from mpy_app_template import boards


def tree(*paths):
    """A GitHub tree response listing the given paths."""
    return {"truncated": False, "tree": [{"path": p} for p in paths]}


@pytest.fixture(autouse=True)
def clear_cache():
    boards._board_cache.clear()
    yield
    boards._board_cache.clear()


@pytest.fixture
def fake_tree(monkeypatch):
    """Serve a canned tree response, and count the requests made."""
    calls = []

    def install(payload):
        def urlopen(request, timeout=None):
            calls.append(request.full_url)
            return _Response(json.dumps(payload).encode())

        monkeypatch.setattr(boards.urllib.request, "urlopen", urlopen)
        return calls

    return install


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_finds_boards_by_their_board_json(fake_tree):
    fake_tree(tree(
        "ports/stm32/boards/PYBV11/board.json",
        "ports/stm32/boards/NUCLEO_H563ZI/board.json",
        "ports/rp2/boards/RPI_PICO/board.json",
    ))
    assert boards.boards_for("stm32") == ["NUCLEO_H563ZI", "PYBV11"]
    assert boards.boards_for("rp2") == ["RPI_PICO"]


def test_ignores_directories_without_a_board_json(fake_tree):
    fake_tree(tree(
        "ports/stm32/boards/PYBV11/board.json",
        "ports/stm32/boards/LEGACY/mpconfigboard.h",  # no board.json
        "ports/stm32/boards/manifest.py",             # a file, not a board
        "ports/stm32/boards/PYBV11/pins.csv",         # inside a board
        "ports/stm32/main.c",
    ))
    assert boards.boards_for("stm32") == ["PYBV11"]


def test_unknown_port_has_no_boards(fake_tree):
    fake_tree(tree("ports/stm32/boards/PYBV11/board.json"))
    assert boards.boards_for("nonesuch") == []


def test_one_request_serves_every_lookup(fake_tree):
    calls = fake_tree(tree(
        "ports/stm32/boards/PYBV11/board.json",
        "ports/rp2/boards/RPI_PICO/board.json",
    ))
    boards.boards_for("stm32")
    boards.boards_for("rp2")
    boards.boards_for("stm32")
    assert len(calls) == 1


def test_ref_comes_from_the_environment(monkeypatch, fake_tree):
    calls = fake_tree(tree("ports/stm32/boards/PYBV11/board.json"))
    monkeypatch.setenv("MPY_BOARDS_REF", "v1.99.0")
    boards.boards_for("stm32")
    assert "v1.99.0" in calls[0]


def test_truncated_listing_is_an_error(monkeypatch):
    payload = {"truncated": True, "tree": [{"path": "ports/stm32/boards/PYBV11/board.json"}]}

    def urlopen(request, timeout=None):
        return _Response(json.dumps(payload).encode())

    monkeypatch.setattr(boards.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="truncated"):
        boards.boards_for("stm32")


def test_network_failure_says_what_to_do(monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(boards.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="network access"):
        boards.boards_for("stm32")


def test_ports_exclude_the_host_binary_ones(monkeypatch, fake_tree):
    fake_tree(tree(
        "ports/stm32/boards/PYBV11/board.json",
        "ports/webassembly/boards/W/board.json",
    ))
    monkeypatch.setattr(
        "mpbuild.build.BUILD_CONTAINERS",
        {"stm32": "x", "webassembly": "x", "unix": "x"},
    )
    assert boards.mpbuild_ports() == ["stm32", "unix"]


def test_ports_drop_those_with_no_boards(monkeypatch, fake_tree):
    fake_tree(tree("ports/stm32/boards/PYBV11/board.json"))
    monkeypatch.setattr(
        "mpbuild.build.BUILD_CONTAINERS", {"stm32": "x", "baochip": "x"}
    )
    # baochip is buildable by mpbuild but has nothing to start a project from.
    assert boards.mpbuild_ports() == ["stm32"]


def test_port_boards_maps_every_offered_port(monkeypatch, fake_tree):
    fake_tree(tree(
        "ports/stm32/boards/PYBV11/board.json",
        "ports/rp2/boards/RPI_PICO/board.json",
    ))
    monkeypatch.setattr(
        "mpbuild.build.BUILD_CONTAINERS", {"stm32": "x", "rp2": "x", "unix": "x"}
    )
    assert boards.port_boards() == {
        "stm32": ["PYBV11"],
        "rp2": ["RPI_PICO"],
        "unix": [],
    }
