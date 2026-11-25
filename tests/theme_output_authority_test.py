"""Output admission follows the opened file, including renderer replacements."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from django_resume.formats.json_resume import themes
from . import theme_generation_test

cache = theme_generation_test.cache


@pytest.mark.parametrize("replacement", ["symlink", "fifo", "regular", "growing"])
def test_output_replacement_is_refused_without_reading_unadmitted_bytes(
    cache, settings, monkeypatch, replacement
):
    if replacement == "fifo" and not hasattr(os, "mkfifo"):
        pytest.skip("requires POSIX FIFO")
    settings.DJANGO_RESUME_JSON_RESUME_RENDER_MAX_BYTES = 16
    output_paths = []
    read_bytes = []
    secret = cache / "unrelated.html"
    secret.write_text("secret")
    original_open, original_read, original_fstat = os.open, os.read, os.fstat
    original_path_open = Path.open
    replaced = []
    output_fds = []

    def replace(path):
        if path not in output_paths or replaced:
            return
        replaced.append(True)
        if replacement == "growing":
            return
        # Keep the old inode allocated so the filesystem cannot reuse it.
        path.rename(path.with_suffix(".retired"))
        if replacement == "symlink":
            path.symlink_to(secret)
        elif replacement == "fifo":
            os.mkfifo(path)
        else:
            path.write_text("replacement")

    def open_output(path, flags, *args, **kwargs):
        path = Path(path)
        replace(path)
        fd = original_open(path, flags, *args, **kwargs)
        if path in output_paths:
            output_fds.append(fd)
        return fd

    def path_open(path, *args, **kwargs):
        # The old implementation used Path.open after lstat. Avoid hanging that
        # counterfactual on a FIFO while still requiring its rejection.
        mode = args[0] if args else kwargs.get("mode", "r")
        if path in output_paths and mode == "rb":
            replace(path)
            if replacement == "fifo":
                return os.fdopen(original_open(path, os.O_RDONLY | os.O_NONBLOCK), "rb")
            if replacement == "growing":
                with original_path_open(path, "wb") as writer:
                    writer.write(b"x" * 17)
        return original_path_open(path, *args, **kwargs)

    def fstat(fd):
        result = original_fstat(fd)
        if fd in output_fds and replacement == "growing":
            with original_path_open(output_paths[0], "ab") as writer:
                writer.write(b"x" * 17)
        return result

    def read(fd, size):
        result = original_read(fd, size)
        if fd in output_fds:
            read_bytes.append(result)
        return result

    def render(command, *, cwd, timeout, file_size_limit):
        output = Path(command[command.index("--output") + 1])
        output.write_text("valid")
        output_paths.append(output)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(themes, "_run_process", render)
    monkeypatch.setattr(os, "open", open_output)
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "fstat", fstat)
    monkeypatch.setattr(Path, "open", path_open)
    with pytest.raises(themes.JsonResumeThemeError):
        themes.render_catalog_theme(SimpleNamespace(), "even")
    assert replaced == [True]
    if replacement != "growing":
        assert read_bytes == []
    else:
        assert sum(map(len, read_bytes)) <= 17
    assert secret.read_text() == "secret"
    assert not output_paths[0].parent.exists()


@pytest.mark.parametrize("mutation", ["rewrite", "truncate", "replace", "stable"])
def test_output_read_requires_one_descriptor_generation(cache, monkeypatch, mutation):
    output_paths, output_fds, changed = [], [], []
    original_open, original_read = os.open, os.read
    body = b"a" * 65536 + b"b" * 65536

    def render(command, *, cwd, timeout, file_size_limit):
        output = Path(command[command.index("--output") + 1])
        output.write_bytes(body)
        output_paths.append(output)
        return SimpleNamespace(returncode=0)

    def open_output(path, flags, *args, **kwargs):
        fd = original_open(path, flags, *args, **kwargs)
        if Path(path) in output_paths:
            output_fds.append(fd)
        return fd

    def read(fd, size):
        chunk = original_read(fd, size)
        if fd in output_fds and chunk and not changed:
            changed.append(True)
            path = output_paths[0]
            if mutation == "replace":
                replacement = path.with_suffix(".new")
                replacement.write_bytes(b"c" * len(body))
                replacement.replace(path)
            elif mutation != "stable":
                path.write_bytes(b"c" * (len(body) if mutation == "rewrite" else 16))
        return chunk

    monkeypatch.setattr(themes, "_run_process", render)
    monkeypatch.setattr(os, "open", open_output)
    monkeypatch.setattr(os, "read", read)
    if mutation == "stable":
        assert (
            themes.render_catalog_theme(SimpleNamespace(), "even").html == body.decode()
        )
    else:
        with pytest.raises(themes.JsonResumeThemeError, match="output changed"):
            themes.render_catalog_theme(SimpleNamespace(), "even")


@pytest.mark.parametrize("size", [32, 8192])
def test_renderer_file_growth_is_bounded(cache, settings, monkeypatch, size):
    import sys

    limit = 32
    settings.DJANGO_RESUME_JSON_RESUME_RENDER_MAX_BYTES = limit
    renderer = themes._resumed_bin(cache)
    renderer.write_text(
        f"#!{sys.executable}\n"
        "import errno, sys\n"
        "with open(sys.argv[-1], 'wb', buffering=0) as output:\n"
        "    try:\n"
        f"        remaining = {size}\n"
        "        while remaining:\n"
        "            remaining -= output.write(b'x' * remaining)\n"
        "    except OSError as error:\n"
        "        if error.errno != errno.EFBIG:\n"
        "            raise\n"
    )
    renderer.chmod(0o755)

    run_process = themes._run_process
    staged = []

    def measure(command, **kwargs):
        completed = run_process(command, **kwargs)
        output = Path(command[-1])
        staged.append((output, output.stat().st_size))
        return completed

    monkeypatch.setattr(themes, "_run_process", measure)
    if size > limit:
        with pytest.raises(themes.JsonResumeThemeError, match="exceeds maximum size"):
            themes.render_catalog_theme(SimpleNamespace(), "even")
        assert staged[0][1] == limit + 1
    else:
        assert themes.render_catalog_theme(SimpleNamespace(), "even").html == "x" * size
        assert staged[0][1] == size
    assert not staged[0][0].parent.exists()


def test_theme_install_uses_inherited_file_size_limit(cache, settings, monkeypatch):
    import sys

    settings.DJANGO_RESUME_JSON_RESUME_RENDER_MAX_BYTES = 32
    npm = cache / "fake-npm"
    npm.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('installed-file').write_bytes(b'x' * 8192)\n"
    )
    npm.chmod(0o755)
    monkeypatch.setattr(themes.shutil, "which", lambda name: str(npm))

    themes.install_catalog_theme("even")

    generation = themes._active_generation(cache)
    assert (generation / "installed-file").stat().st_size == 8192
