"""Cross-process tests use spawn on every platform and synthetic output."""

import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace

import pytest


def _seed_cache(target, renderer_version="7.0.0"):
    from django_resume.formats.json_resume import themes

    binary = themes._resumed_bin(target)
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("synthetic renderer")
    for package, version in [
        ("jsonresume-theme-even", "0.26.1"),
        ("resumed", renderer_version),
    ]:
        package_dir = target / "node_modules" / package
        package_dir.mkdir(exist_ok=True)
        (package_dir / "package.json").write_text(json.dumps({"version": version}))


def _cache_worker(
    target, action, attempted, entered, release, result, lock_timeout, fail
):
    import django

    django.setup()
    from django.conf import settings
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    settings.DJANGO_RESUME_JSON_RESUME_CACHE_LOCK_TIMEOUT = lock_timeout
    themes.shutil.which = lambda name: "synthetic-npm"
    themes.export_resume = lambda resume: SimpleNamespace(
        document={"basics": {"name": "Synthetic"}},
        report=SimpleNamespace(valid=True, notes=()),
    )
    themes.portable_document = lambda document: document

    def run(command, *, cwd, timeout):
        entered.set()
        if action == "install":
            if fail:
                raise themes.JsonResumeThemeError("synthetic install failure")
            themes._resumed_bin(Path(target)).unlink()
            if not release.wait(5):
                raise RuntimeError("test did not release install")
            _seed_cache(Path(target))
        else:
            Path(command[command.index("--output") + 1]).write_text("<p>complete</p>")
        return SimpleNamespace(returncode=0)

    themes._run_process = run
    attempted.set()
    try:
        if action == "install":
            themes.install_catalog_theme("even")
        elif action == "readiness":
            ready = themes.catalog_theme_installed(themes.catalog_theme("even"))
            entered.set()
            if not ready:
                raise RuntimeError("observed partial cache")
        else:
            rendered = themes.render_catalog_theme(SimpleNamespace(), "even")
            if rendered.html != "<p>complete</p>":
                raise RuntimeError("unexpected output")
        result.put("ok")
    except Exception as exc:
        result.put(f"{type(exc).__name__}: {exc}")


def _start(ctx, target, action, *, lock_timeout=5, fail=False):
    attempted, entered, release = [ctx.Event() for _ in range(3)]
    result = ctx.Queue()
    process = ctx.Process(
        target=_cache_worker,
        args=(
            str(target),
            action,
            attempted,
            entered,
            release,
            result,
            lock_timeout,
            fail,
        ),
    )
    process.start()
    return process, attempted, entered, release, result


def _finish(worker):
    process, _, _, _, result = worker
    process.join(8)
    assert not process.is_alive()
    assert process.exitcode == 0
    return result.get(timeout=2)


def _cleanup(*workers):
    for worker in workers:
        worker[3].set()
    for worker in workers:
        worker[0].join(8)
        if worker[0].is_alive():
            worker[0].terminate()
            worker[0].join(2)


@pytest.mark.parametrize("action", ["render", "readiness"])
def test_install_serializes_readiness_and_render_across_processes(tmp_path, action):
    _seed_cache(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    installer = _start(ctx, tmp_path, "install")
    follower = None
    try:
        assert installer[2].wait(5)
        follower = _start(ctx, tmp_path, action)
        assert follower[1].wait(5)
        assert not follower[2].wait(0.2)
        installer[3].set()
        assert _finish(installer) == "ok"
        assert _finish(follower) == "ok"
    finally:
        _cleanup(installer, *([follower] if follower else []))


def test_cache_contention_times_out_and_releases_after_install(tmp_path):
    _seed_cache(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    installer = _start(ctx, tmp_path, "install")
    follower = recovery = None
    try:
        assert installer[2].wait(5)
        follower = _start(ctx, tmp_path, "render", lock_timeout=0.1)
        assert "JsonResumeThemeError: JSON Resume theme cache is busy" in _finish(
            follower
        )
        installer[3].set()
        assert _finish(installer) == "ok"
        recovery = _start(ctx, tmp_path, "render")
        assert _finish(recovery) == "ok"
    finally:
        _cleanup(installer, *[worker for worker in [follower, recovery] if worker])


def test_failed_install_releases_cache_lock(tmp_path):
    _seed_cache(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    installer = _start(ctx, tmp_path, "install", fail=True)
    renderer = None
    try:
        assert "synthetic install failure" in _finish(installer)
        renderer = _start(ctx, tmp_path, "render")
        assert _finish(renderer) == "ok"
    finally:
        _cleanup(installer, *([renderer] if renderer else []))


@pytest.mark.parametrize("version", [None, "0.0.1", "7.0.0", "8.0.0"])
@pytest.mark.parametrize("configured", ["7.0.0", "8.0.0"])
def test_catalog_readiness_requires_renderer_pin(
    tmp_path, settings, version, configured
):
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path
    settings.DJANGO_RESUME_JSON_RESUME_RESUMED_VERSION = configured
    _seed_cache(tmp_path, version)
    if version is None:
        (tmp_path / "node_modules" / "resumed" / "package.json").unlink()
    assert themes.catalog_theme_installed(themes.catalog_theme("even")) is (
        version == configured
    )


@pytest.mark.parametrize(
    "configured", [None, "bad", True, 0, -1, float("inf"), float("nan")]
)
def test_invalid_cache_wait_is_theme_error(settings, configured):
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_CACHE_LOCK_TIMEOUT = configured
    with pytest.raises(themes.JsonResumeThemeError, match="positive and finite"):
        themes.catalog_theme_installed(themes.catalog_theme("even"))


@pytest.mark.parametrize("failure_point", ["directory", "lock"])
@pytest.mark.parametrize("operation", ["readiness", "install"])
def test_inaccessible_cache_is_theme_error(
    tmp_path, settings, monkeypatch, failure_point, operation
):
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path

    def denied(*args, **kwargs):
        raise PermissionError("synthetic denial")

    monkeypatch.setattr(
        themes, "cache_dir" if failure_point == "directory" else "FileLock", denied
    )
    monkeypatch.setattr(themes.shutil, "which", lambda name: "synthetic-npm")
    with pytest.raises(themes.JsonResumeThemeError, match="could not be accessed"):
        if operation == "install":
            themes.install_catalog_theme("even")
        else:
            themes.catalog_theme_installed(themes.catalog_theme("even"))


def test_saved_catalog_selection_checks_pins(tmp_path, settings):
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path
    _seed_cache(tmp_path, "0.0.1")
    resume = SimpleNamespace(
        integration_data={"json_resume": {"theme": {"key": "even"}}}
    )
    with pytest.raises(themes.CatalogThemeNotInstalled, match="pinned"):
        themes.render_selected_theme(resume)
