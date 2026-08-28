"""Tests for the project creation command."""

from pathlib import Path

import pytest

from mpy_app_template import cli


@pytest.fixture
def captured(monkeypatch):
    """Record what the command would hand to copier."""
    calls = {}

    def run_copy(src, dst, **kwargs):
        calls["copy"] = (src, dst, kwargs)

    def run_update(dst, **kwargs):
        calls["update"] = (dst, kwargs)

    monkeypatch.setattr("copier.run_copy", run_copy)
    monkeypatch.setattr("copier.run_update", run_update)
    monkeypatch.setattr(
        "mpy_app_template.boards.port_boards",
        lambda: {"stm32": ["PYBV11"], "rp2": ["RPI_PICO"]},
    )
    return calls


def test_passes_the_board_map_to_copier(captured, tmp_path):
    cli.main([str(tmp_path / "proj")])
    _, _, kwargs = captured["copy"]
    assert kwargs["data"]["port_boards"] == {"stm32": ["PYBV11"], "rp2": ["RPI_PICO"]}


def test_creates_the_destination(captured, tmp_path):
    dest = tmp_path / "proj"
    cli.main([str(dest)])
    assert dest.is_dir()


def test_answers_file_is_merged_without_copier_internals(captured, tmp_path):
    answers = tmp_path / "answers.yml"
    answers.write_text(
        "_commit: HEAD\n_src_path: /somewhere\nproject_name: Widget\ntarget_port: rp2\n"
    )
    cli.main(["--data-file", str(answers), str(tmp_path / "proj")])
    _, _, kwargs = captured["copy"]
    data = kwargs["data"]
    assert data["project_name"] == "Widget"
    assert data["target_port"] == "rp2"
    assert "port_boards" in data
    assert not any(key.startswith("_") for key in data)


def test_an_answers_file_implies_no_prompting(captured, tmp_path):
    answers = tmp_path / "answers.yml"
    answers.write_text("project_name: Widget\n")
    cli.main(["--data-file", str(answers), str(tmp_path / "proj")])
    assert captured["copy"][2]["defaults"] is True


def test_prompts_when_no_answers_file(captured, tmp_path):
    cli.main([str(tmp_path / "proj")])
    assert captured["copy"][2]["defaults"] is False


def test_update_reapplies_in_place(captured, tmp_path):
    dest = tmp_path / "proj"
    dest.mkdir()
    cli.main(["--update", str(dest)])
    assert "copy" not in captured
    target, kwargs = captured["update"]
    assert Path(target) == dest
    assert kwargs["data"]["port_boards"]


def test_template_source_defaults_to_the_repository(captured, tmp_path):
    cli.main([str(tmp_path / "proj")])
    src, _, kwargs = captured["copy"]
    assert src == cli.TEMPLATE_URL
    assert kwargs["vcs_ref"] == "main"
