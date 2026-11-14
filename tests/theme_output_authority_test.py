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

    def render(command, *, cwd, timeout):
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
