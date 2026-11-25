import os
import sys
from contextlib import contextmanager

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


def test_installed_layout_requires_explicit_root(monkeypatch, tmp_path, capsys):
    installed = tmp_path / "lib" / "site-packages" / "django_resume" / "entrypoints"
    installed.mkdir(parents=True)
    module = installed / "llm_content.py"
    module.write_text("# synthetic installed module")
    (installed.parents[1] / "unrelated.py").write_text("UNRELATED_SENTINEL")
    monkeypatch.setattr(cli, "__file__", str(module))
    monkeypatch.setattr(sys, "argv", ["llm-content"])
    with pytest.raises(SystemExit) as error:
        cli.llm_content()
    assert error.value.code != 0
    result = capsys.readouterr()
    assert result.out == ""
    assert "--root" in result.err
    assert "UNRELATED_SENTINEL" not in result.err


def test_explicit_root_from_installed_layout(monkeypatch, tmp_path, capsys):
    (tmp_path / "source.py").write_text("synthetic source")
    monkeypatch.setattr(
        cli, "__file__", "/synthetic/site-packages/entrypoints/llm_content.py"
    )
    monkeypatch.setattr(
        sys, "argv", ["llm-content", "--root", str(tmp_path), "--paths-only"]
    )
    assert cli.llm_content() == 0
    assert capsys.readouterr().out == "source.py\n"


def test_checkout_root_selection():
    from pathlib import Path

    assert cli.get_project_root() == Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("root", ["missing", "file"])
def test_explicit_root_must_be_directory(monkeypatch, tmp_path, capsys, root):
    (tmp_path / "file").write_text("synthetic")
    monkeypatch.setattr(sys, "argv", ["llm-content", "--root", str(tmp_path / root)])
    with pytest.raises(SystemExit) as error:
        cli.llm_content()
    assert error.value.code != 0
    assert capsys.readouterr().out == ""


def test_context_per_file_limit_checks_actual_reads(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "MAX_FILE_BYTES", 8, raising=False)
    (tmp_path / "large.py").write_text("x" * 9)
    assert run_cli(monkeypatch, tmp_path) != 0
    result = capsys.readouterr()
    assert result.out == ""
    assert "limit" in result.err


def test_context_growth_after_inventory_is_bounded(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "MAX_FILE_BYTES", 8, raising=False)
    source = tmp_path / "grow.py"
    source.write_text("x")
    real_open = os.open

    def grow_before_open(path, flags, *args, **kwargs):
        if path == "grow.py":
            source.write_text("x" * 9)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", grow_before_open)
    assert run_cli(monkeypatch, tmp_path) != 0
    assert capsys.readouterr().out == ""


def test_context_refuses_source_rewritten_during_read(monkeypatch, tmp_path, capsys):
    (tmp_path / "a.py").write_text("stable source")
    path = tmp_path / "z.py"
    path.write_bytes(b"old source")
    original = path.stat()
    open_source = cli.open_source

    @contextmanager
    def open_rewritten_source(root_fd, relative_path):
        with open_source(root_fd, relative_path) as source:
            if relative_path.name == path.name:

                def rewrite_during_read(size):
                    prefix = source.raw.read(3)
                    path.write_bytes(b"new script")
                    os.utime(
                        path, ns=(original.st_atime_ns, original.st_mtime_ns + 10**9)
                    )
                    return prefix + source.raw.read(size - len(prefix))

                monkeypatch.setattr(source, "read", rewrite_during_read)
            yield source

    monkeypatch.setattr(cli, "open_source", open_rewritten_source)
    assert run_cli(monkeypatch, tmp_path) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "refused" in result.err


def test_context_aggregate_limit_counts_headers_and_utf8(monkeypatch, tmp_path, capsys):
    for name in ("a.py", "z.py"):
        (tmp_path / name).write_text("é" * 4, encoding="utf-8")
    expected = "".join(
        f"{tmp_path / name}\n{name}\n---\néééé\n---\n" for name in ("a.py", "z.py")
    )
    monkeypatch.setattr(
        cli, "MAX_EXPORT_BYTES", len(expected.encode("utf-8")), raising=False
    )
    assert run_cli(monkeypatch, tmp_path) == 0
    assert capsys.readouterr().out == expected
    monkeypatch.setattr(cli, "MAX_EXPORT_BYTES", len(expected.encode("utf-8")) - 1)
    assert run_cli(monkeypatch, tmp_path) != 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("matched", [True, False])
def test_context_tree_entry_limit(monkeypatch, tmp_path, capsys, matched):
    monkeypatch.setattr(cli, "MAX_TREE_ENTRIES", 2, raising=False)
    suffix = "py" if matched else "dat"
    for i in range(3):
        (tmp_path / f"{i}.{suffix}").write_text("small")
    assert run_cli(monkeypatch, tmp_path, "--paths-only") != 0
    assert capsys.readouterr().out == ""


def test_context_paths_only_never_opens_contents(monkeypatch, tmp_path, capsys):
    (tmp_path / "z.py").write_bytes(b"\xff")
    (tmp_path / "a.py").write_text("x" * 20)
    monkeypatch.setattr(cli, "MAX_FILE_BYTES", 1, raising=False)
    real_open = os.open

    def no_content_open(path, flags, *args, **kwargs):
        assert path not in ("a.py", "z.py")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", no_content_open)
    assert run_cli(monkeypatch, tmp_path, "--paths-only") == 0
    assert capsys.readouterr().out == "a.py\nz.py\n"


@pytest.mark.parametrize("args", [(), ("--paths-only",)])
@pytest.mark.parametrize("separator", ["\n", "\r", "\u2028"])
def test_context_refuses_path_record_separators(
    monkeypatch, tmp_path, capsys, args, separator
):
    (tmp_path / "a.py").write_text("valid")
    (tmp_path / f"z{separator}extra.py").write_text("synthetic source")
    assert run_cli(monkeypatch, tmp_path, *args) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "refused" in result.err


def test_context_checks_root_only_when_written_to_output(monkeypatch, tmp_path, capsys):
    root = tmp_path / "project\nextra"
    root.mkdir()
    (root / "café.py").write_text("synthetic source")
    assert run_cli(monkeypatch, root) == 1
    assert capsys.readouterr().out == ""
    assert run_cli(monkeypatch, root, "--paths-only") == 0
    assert capsys.readouterr().out == "café.py\n"


def test_context_rejects_non_utf8_without_partial_stdout(monkeypatch, tmp_path, capsys):
    (tmp_path / "a.py").write_text("valid")
    (tmp_path / "z.py").write_bytes(b"\xff")
    assert run_cli(monkeypatch, tmp_path) != 0
    assert capsys.readouterr().out == ""


def test_directory_replacement_symlink_cannot_escape(monkeypatch, tmp_path, capsys):
    root = tmp_path / "project"
    directory = root / "nested"
    directory.mkdir(parents=True)
    (directory / "source.py").write_text("inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "source.py").write_text("OUTSIDE_SENTINEL")
    real_open = os.open
    directory_opens = 0

    def swap_directory(path, flags, *args, **kwargs):
        nonlocal directory_opens
        if path == "nested":
            directory_opens += 1
            if directory_opens == 2:  # after inventory, before content traversal
                directory.rename(root / "retired")
                directory.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_directory)
    assert run_cli(monkeypatch, root) != 0
    result = capsys.readouterr()
    assert result.out == ""
    assert "OUTSIDE_SENTINEL" not in result.err


def test_context_fifo_is_refused_without_open(monkeypatch, tmp_path, capsys):
    os.mkfifo(tmp_path / "pipe.py")
    assert run_cli(monkeypatch, tmp_path) != 0
    assert capsys.readouterr().out == ""


def test_context_depth_and_inventory_path_limits(monkeypatch, tmp_path, capsys):
    directory = tmp_path / "nested"
    directory.mkdir()
    (directory / "source.py").write_text("inside")
    monkeypatch.setattr(cli, "MAX_TREE_DEPTH", 0)
    assert run_cli(monkeypatch, tmp_path, "--paths-only") != 0
    assert capsys.readouterr().out == ""
    monkeypatch.setattr(cli, "MAX_TREE_DEPTH", 1)
    monkeypatch.setattr(cli, "MAX_EXPORT_BYTES", len("nested/source.py".encode()) - 1)
    assert run_cli(monkeypatch, tmp_path, "--paths-only") != 0
    assert capsys.readouterr().out == ""


def test_context_per_file_exact_boundary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "MAX_FILE_BYTES", 8)
    (tmp_path / "source.py").write_text("é" * 4, encoding="utf-8")
    assert run_cli(monkeypatch, tmp_path) == 0
    assert "éééé" in capsys.readouterr().out
