"""Install failures must never mutate the renderer's active generation."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def seed(target, versions=None):
    from django_resume.formats.json_resume import themes

    versions = versions or {"resumed": "7.0.0", "jsonresume-theme-even": "0.26.1"}
    target.mkdir(parents=True, exist_ok=True)
    (target / "package.json").write_text(json.dumps({"dependencies": versions}))
    for package, version in versions.items():
        directory = target / "node_modules" / package
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "package.json").write_text(json.dumps({"version": version}))
    binary = themes._resumed_bin(target)
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("complete")


def fake_npm(command, *, cwd, timeout):
    versions = (
        json.loads((cwd / "package.json").read_text())["dependencies"]
        if (cwd / "package.json").exists()
        else {}
    )
    for spec in command[command.index("--save-exact") + 1 :]:
        name, separator, version = spec.rpartition("@")
        if not separator or not name:
            name, version = spec, "1.0.0"
        versions[name] = version
    seed(cwd, versions)
    return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture
def cache(tmp_path, settings, monkeypatch):
    from django_resume.formats.json_resume import themes

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path
    seed(tmp_path)
    monkeypatch.setattr(themes.shutil, "which", lambda name: "synthetic-npm")
    monkeypatch.setattr(
        themes,
        "export_resume",
        lambda resume: SimpleNamespace(
            document={}, report=SimpleNamespace(valid=True, notes=())
        ),
    )
    monkeypatch.setattr(themes, "portable_document", lambda document: document)
    return tmp_path


def assert_renders(monkeypatch, expected="complete"):
    from django_resume.formats.json_resume import themes

    def render(command, *, cwd, timeout):
        assert (
            themes._installed_package_version(cwd, "jsonresume-theme-even") == "0.26.1"
        )
        assert themes._installed_package_version(cwd, "resumed") == "7.0.0"
        Path(command[command.index("--output") + 1]).write_text(
            themes._resumed_bin(cwd).read_text()
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(themes, "_run_process", render)
    assert themes.render_catalog_theme(SimpleNamespace(), "even").html == expected


@pytest.mark.parametrize(
    "failure", ["exit", "interrupt", "incomplete", "lost_existing"]
)
def test_failed_generation_keeps_working_renderer(cache, monkeypatch, failure):
    from django_resume.formats.json_resume import themes

    def broken(command, *, cwd, timeout):
        themes._resumed_bin(cwd).write_text("broken")
        if failure == "interrupt":
            raise KeyboardInterrupt
        if failure == "incomplete":
            themes._resumed_bin(cwd).unlink()
            return SimpleNamespace(returncode=0)
        if failure == "lost_existing":
            fake_npm(command, cwd=cwd, timeout=timeout)
            (cwd / "node_modules/jsonresume-theme-even/package.json").unlink()
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1, stderr="synthetic failure", stdout="")

    monkeypatch.setattr(themes, "_run_process", broken)
    with pytest.raises(
        KeyboardInterrupt if failure == "interrupt" else themes.JsonResumeThemeError
    ):
        themes.install_catalog_theme("flat")
    assert_renders(monkeypatch)


def test_successful_generation_is_complete_and_preserves_old_theme(cache, monkeypatch):
    from django_resume.formats.json_resume import themes

    prefixes = []

    def install(command, *, cwd, timeout):
        prefixes.append(cwd)
        result = fake_npm(command, cwd=cwd, timeout=timeout)
        themes._resumed_bin(cwd).write_text("new complete")
        return result

    monkeypatch.setattr(themes, "_run_process", install)
    themes.install_catalog_theme("flat")
    assert prefixes[0] != cache
    assert themes.catalog_theme_installed(themes.catalog_theme("flat"))
    assert_renders(monkeypatch, "new complete")
    monkeypatch.setattr(themes, "_run_process", install)
    themes.install_catalog_theme("flat")
    assert not prefixes[0].exists()  # no renderer owns it outside the shared lock
    assert_renders(monkeypatch, "new complete")


def _crash_installer(target, barrier, reached, unsafe):
    import django

    django.setup()
    from django_resume.formats.json_resume import themes
    from django.conf import settings

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    root = Path(target)
    themes.shutil.which = lambda name: "synthetic-npm"

    def stop(phase):
        if phase == barrier:
            reached.set()
            # The parent kills this process; no Python exception cleanup runs.
            import time

            while True:
                time.sleep(0.1)

    def install(command, *, cwd, timeout):
        themes._resumed_bin(cwd).write_text("partial")
        stop("creation")
        fake_npm(command, cwd=cwd, timeout=timeout)
        themes._resumed_bin(cwd).write_text("new")
        (cwd / "node_modules/jsonresume-theme-even/revision").write_text("new")
        return SimpleNamespace(returncode=0)

    themes._run_process = install
    verify = themes._verify_generation
    replace = themes.os.replace

    def verify_at_barrier(*args):
        verify(*args)
        stop("verification")

    def replace_at_barrier(source, destination):
        stop("publication")
        replace(source, destination)
        stop("published")

    themes._verify_generation = verify_at_barrier
    themes.os.replace = replace_at_barrier
    if unsafe:
        # Counterfactual: the former implementation ran npm in the live cache.
        with themes._theme_cache_lock():
            install(
                ["--save-exact", "resumed@7.0.0", "jsonresume-theme-flat@0.3.7"],
                cwd=root,
                timeout=5,
            )
    else:
        themes.install_catalog_theme("flat")


def _restart_renderer(target, result):
    import django

    django.setup()
    from django_resume.formats.json_resume import themes
    from django.conf import settings

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    settings.DJANGO_RESUME_JSON_RESUME_CACHE_LOCK_TIMEOUT = 1
    themes.export_resume = lambda resume: SimpleNamespace(
        document={}, report=SimpleNamespace(valid=True, notes=())
    )
    themes.portable_document = lambda document: document

    def render(command, *, cwd, timeout):
        assert "--output" in command, "ordinary rendering must never install"
        renderer = themes._resumed_bin(cwd).read_text()
        revision = (cwd / "node_modules/jsonresume-theme-even/revision").read_text()
        assert renderer == revision, "mixed or incomplete generation"
        assert themes._installed_package_version(cwd, "resumed") == "7.0.0"
        assert (
            themes._installed_package_version(cwd, "jsonresume-theme-even") == "0.26.1"
        )
        Path(command[command.index("--output") + 1]).write_text(renderer)
        return SimpleNamespace(returncode=0)

    themes._run_process = render
    try:
        result.put(themes.render_catalog_theme(SimpleNamespace(), "even").html)
    except Exception as exc:
        result.put(f"refused: {exc}")


def crash_and_restart(cache, barrier, unsafe=False):
    from django_resume.formats.json_resume import themes
    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    themes._resumed_bin(cache).write_text("old")
    (cache / "node_modules/jsonresume-theme-even/revision").write_text("old")
    reached = ctx.Event()
    installer = ctx.Process(
        target=_crash_installer, args=(str(cache), barrier, reached, unsafe)
    )
    installer.start()
    try:
        assert reached.wait(10), f"installer did not reach {barrier}"
    finally:
        installer.kill()
        installer.join(5)
    assert not installer.is_alive()
    assert installer.exitcode != 0
    result = ctx.Queue()
    renderer = ctx.Process(target=_restart_renderer, args=(str(cache), result))
    renderer.start()
    try:
        renderer.join(10)
        assert not renderer.is_alive()
        assert renderer.exitcode == 0
        return result.get(timeout=2)
    finally:
        if renderer.is_alive():
            renderer.kill()
            renderer.join(5)
        result.close()
        result.join_thread()


@pytest.mark.parametrize(
    "barrier", ["creation", "verification", "publication", "published"]
)
def test_killed_install_restarts_with_one_complete_generation(cache, barrier):
    assert crash_and_restart(cache, barrier) == (
        "new" if barrier == "published" else "old"
    )


def test_crash_oracle_detects_former_in_place_mutation(cache):
    assert crash_and_restart(cache, "creation", unsafe=True).startswith("refused:")


def test_relative_cache_path_retains_published_generation(
    tmp_path, settings, monkeypatch
):
    from django_resume.formats.json_resume import themes

    monkeypatch.chdir(tmp_path)
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = "relative-cache"
    monkeypatch.setattr(themes.shutil, "which", lambda name: "synthetic-npm")
    monkeypatch.setattr(themes, "_run_process", fake_npm)
    themes.install_catalog_theme("even")
    themes.install_catalog_theme("flat")
    assert themes.catalog_theme_installed(themes.catalog_theme("even"))
    assert themes.catalog_theme_installed(themes.catalog_theme("flat"))
