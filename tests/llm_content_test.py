import os
import sys

import pytest

from django_resume.entrypoints import llm_content as cli


def run_cli(monkeypatch, root, *args):
    monkeypatch.setattr(cli, "get_project_root", lambda: root)
    monkeypatch.setattr(sys, "argv", ["llm-content", *args])
    return cli.llm_content()


@pytest.mark.parametrize("paths_only", [False, True])
def test_refuses_file_symlinks(monkeypatch, tmp_path, capsys, paths_only):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "private.py"
    outside.write_text("OUTSIDE_SENTINEL")
    (root / "linked.py").symlink_to(outside)
    assert run_cli(monkeypatch, root, *(["--paths-only"] if paths_only else [])) != 0
    result = capsys.readouterr()
    assert "OUTSIDE_SENTINEL" not in result.out + result.err
    assert "refused" in result.err


def test_swap_before_open_cannot_escape(monkeypatch, tmp_path, capsys):
    source = tmp_path / "source.py"
    source.write_text("inside")
    outside = tmp_path.parent / (tmp_path.name + "-outside.py")
    outside.write_text("OUTSIDE_SENTINEL")
    real_open = os.open

    def swap_open(path, flags, *args, **kwargs):
        if path == "source.py":
            source.unlink()
            source.symlink_to(outside)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_open)
    try:
        assert run_cli(monkeypatch, tmp_path) != 0
        result = capsys.readouterr()
        assert "OUTSIDE_SENTINEL" not in result.out + result.err
    finally:
        outside.unlink()


def test_regular_source_and_directory_links(monkeypatch, tmp_path, capsys):
    (tmp_path / "source.py").write_text("synthetic source")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert run_cli(monkeypatch, tmp_path) == 0
    output = capsys.readouterr().out
    assert "synthetic source" in output
    assert output.count("synthetic source") == 1
