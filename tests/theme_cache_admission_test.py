"""Damaged/restored caches never acquire renderer or installer authority."""

import os
from types import SimpleNamespace

import pytest

from django_resume.formats.json_resume import themes
from . import theme_generation_test
from .theme_generation_test import seed

cache = theme_generation_test.cache


@pytest.mark.parametrize(
    "kind",
    ["generation-link", "marker-link", "marker-fifo", "marker-large", "root-link"],
)
def test_cache_refuses_redirected_generation(cache, tmp_path, monkeypatch, kind):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    seed(outside)
    generation = cache / "generation-valid"
    marker = cache / ".current"
    if kind == "generation-link":
        generation.symlink_to(outside, target_is_directory=True)
        marker.write_text(generation.name)
    elif kind == "marker-link":
        (outside / "pointer").write_text("generation-valid")
        marker.symlink_to(outside / "pointer")
    elif kind == "marker-fifo":
        os.mkfifo(marker)
    elif kind == "marker-large":
        marker.write_text("generation-" + "a" * 4096)
    else:
        moved = cache.with_name(cache.name + "-moved")
        cache.rename(moved)
        cache.symlink_to(outside, target_is_directory=True)
    calls = []
    monkeypatch.setattr(themes, "_run_process", lambda *a, **kw: calls.append(True))
    with pytest.raises(themes.JsonResumeThemeError):
        themes.render_catalog_theme(SimpleNamespace(), "even")
    assert calls == []


def test_generation_replacement_before_install_is_refused(cache, monkeypatch):
    seed(cache / "generation-valid")
    (cache / ".current").write_text("generation-valid")
    original = themes._generation_requirements
    calls = []

    def replace(target):
        required = original(target)
        target.rename(cache / "generation-retired")
        seed(target)
        return required

    monkeypatch.setattr(themes, "_generation_requirements", replace)
    monkeypatch.setattr(themes, "_run_process", lambda *a, **kw: calls.append(True))
    with pytest.raises(themes.JsonResumeThemeError, match="changed"):
        themes.install_catalog_theme("flat")
    assert calls == []


@pytest.mark.parametrize("location", ["root", "package"])
@pytest.mark.parametrize(
    "damage", ["large", "fifo", "duplicate", "deep", "scalar", "encoding"]
)
def test_corrupt_manifest_refuses_install_preserves_current(
    cache, monkeypatch, location, damage
):
    manifest = cache / (
        "package.json" if location == "root" else "node_modules/resumed/package.json"
    )
    manifest.unlink()
    if damage == "fifo":
        os.mkfifo(manifest)
    else:
        content = {
            "large": b" " * (1024 * 1024 + 1),
            "duplicate": b'{"version":"7.0.0","version":"8.0.0","dependencies":{},"dependencies":{}}',
            "deep": b'{"extension":' + b"[" * 65 + b"0" + b"]" * 65 + b"}",
            "scalar": b"[]",
            "encoding": b"\xff",
        }[damage]
        manifest.write_bytes(content)
    calls = []
    monkeypatch.setattr(themes, "_run_process", lambda *a, **kw: calls.append(True))
    with pytest.raises(themes.JsonResumeThemeError):
        themes.install_catalog_theme("flat")
    assert calls == []
    assert not (cache / ".current").exists()
    assert themes._resumed_bin(cache).read_text() == "complete"


def test_metadata_reader_bounds_growth(cache, monkeypatch):
    original_read = themes.os.read
    sizes = []

    def growing(fd, size):
        sizes.append(size)
        return b" " * size

    monkeypatch.setattr(themes.os, "read", growing)
    with pytest.raises(themes.JsonResumeThemeError):
        themes._generation_requirements(cache)
    assert sum(sizes) <= 1024 * 1024 + 1
    monkeypatch.setattr(themes.os, "read", original_read)


def test_process_keeps_opened_working_directory(tmp_path, monkeypatch):
    import sys

    working = tmp_path / "working"
    working.mkdir()
    (working / "sentinel").write_text("trusted")
    popen = themes.subprocess.Popen

    def replace_before_launch(*args, **kwargs):
        working.rename(tmp_path / "retired")
        working.mkdir()
        (working / "sentinel").write_text("replacement")
        return popen(*args, **kwargs)

    monkeypatch.setattr(themes.subprocess, "Popen", replace_before_launch)
    result = themes._run_process(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; print(Path('sentinel').read_text())",
        ],
        cwd=working,
        timeout=5,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "trusted"


def test_generation_replacement_during_export_refuses_renderer(cache, monkeypatch):
    seed(cache / "generation-valid")
    (cache / ".current").write_text("generation-valid")
    original = themes.export_resume
    calls = []

    def replace(resume):
        target = cache / "generation-valid"
        target.rename(cache / "generation-retired")
        seed(target)
        return original(resume)

    monkeypatch.setattr(themes, "export_resume", replace)
    monkeypatch.setattr(themes, "_run_process", lambda *a, **kw: calls.append(True))
    with pytest.raises(themes.JsonResumeThemeError, match="changed"):
        themes.render_catalog_theme(SimpleNamespace(), "even")
    assert calls == []


def test_symlinked_cache_ancestor_is_refused(tmp_path, settings):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = alias / "cache"
    with pytest.raises(themes.JsonResumeThemeError):
        themes.catalog_theme_installed(themes.catalog_theme("even"))
    assert not (actual / "cache").exists()
