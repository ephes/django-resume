"""Resource policy and stream failures are admitted before trusting child work."""

import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from django_resume.formats.json_resume import themes


@pytest.mark.parametrize("operation", ["install", "render", "catalog", "process"])
@pytest.mark.parametrize(
    "bad", [True, None, "1", -1, 0, float("nan"), float("inf"), 10**400]
)
def test_invalid_timeout_starts_no_work(
    tmp_path, settings, monkeypatch, operation, bad
):
    target = tmp_path / "absent-cache"
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    popen = Mock()
    monkeypatch.setattr(themes.subprocess, "Popen", popen)
    with pytest.raises(themes.JsonResumeThemeError, match="timeout"):
        if operation == "install":
            themes.install_catalog_theme("even", timeout=bad)
        elif operation == "catalog":
            themes.render_catalog_theme(SimpleNamespace(), "even", timeout=bad)
        elif operation == "render":
            themes.render_theme(SimpleNamespace(), "jsonresume-theme-even", timeout=bad)
        else:
            themes._run_process(["synthetic"], cwd=tmp_path, timeout=bad)
    popen.assert_not_called()
    assert not target.exists()


@pytest.mark.parametrize("setting", ["PROCESS_OUTPUT", "RENDER"])
@pytest.mark.parametrize(
    "bad", [True, None, "10", "bad", -1, 0, 1.5, float("inf"), 10**400]
)
def test_invalid_output_budget_starts_no_work(
    tmp_path, settings, monkeypatch, setting, bad
):
    target = tmp_path / "absent-cache"
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    setattr(settings, f"DJANGO_RESUME_JSON_RESUME_{setting}_MAX_BYTES", bad)
    popen = Mock()
    monkeypatch.setattr(themes.subprocess, "Popen", popen)
    with pytest.raises(themes.JsonResumeThemeError):
        if setting == "PROCESS_OUTPUT":
            themes.install_catalog_theme("even")
        else:
            themes.render_theme(SimpleNamespace(), "jsonresume-theme-even")
    popen.assert_not_called()
    assert not target.exists()


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_reader_failure_refuses_zero_exit_and_cleans_work(
    tmp_path, monkeypatch, stream_name
):
    class Broken(io.BytesIO):
        def read(self, size):
            if self.tell():
                raise OSError("synthetic-sensitive-stream-content")
            return super().read(1)

    process = SimpleNamespace(
        stdout=io.BytesIO(b"{}"),
        stderr=io.BytesIO(b""),
        wait=Mock(return_value=0),
        poll=Mock(return_value=0),
        pid=12345,
    )
    setattr(process, stream_name, Broken(b"{}"))
    monkeypatch.setattr(themes, "_wait_process_exit", Mock())
    killed = Mock()
    monkeypatch.setattr(themes, "_terminate_process_tree", killed)
    monkeypatch.setattr(themes.subprocess, "Popen", Mock(return_value=process))
    with pytest.raises(themes.JsonResumeThemeError, match="read") as error:
        themes._run_process(["synthetic"], cwd=tmp_path, timeout=1)
    assert "sensitive" not in str(error.value)
    assert killed.called
    assert process.wait.called
    assert process.stdout.closed and process.stderr.closed


@pytest.mark.parametrize("bad", ["", "relative/python", "/nonexistent/python3"])
def test_unusable_trampoline_interpreter_starts_no_work(
    tmp_path, settings, monkeypatch, bad
):
    settings.DJANGO_RESUME_JSON_RESUME_PYTHON = bad
    popen = Mock()
    monkeypatch.setattr(themes.subprocess, "Popen", popen)
    with pytest.raises(
        themes.JsonResumeThemeError, match="DJANGO_RESUME_JSON_RESUME_PYTHON"
    ):
        themes._run_process(["synthetic"], cwd=tmp_path, timeout=5)
    popen.assert_not_called()


def test_embedded_host_executable_is_not_used_as_python(tmp_path, monkeypatch):
    # uWSGI/mod_wsgi report their own binary as sys.executable.
    host = tmp_path / "uwsgi"
    host.write_text("#!/bin/sh\nexit 0\n")
    host.chmod(0o755)
    monkeypatch.setattr(themes.sys, "executable", str(host))
    popen = Mock()
    monkeypatch.setattr(themes.subprocess, "Popen", popen)
    with pytest.raises(themes.JsonResumeThemeError, match="Python interpreter"):
        themes._run_process(["synthetic"], cwd=tmp_path, timeout=5)
    popen.assert_not_called()


def test_explicit_interpreter_setting_is_trusted_without_name_heuristic(
    tmp_path, settings, monkeypatch
):
    import sys

    # e.g. RHEL's /usr/libexec/platform-python
    platform_python = tmp_path / "platform-python"
    platform_python.symlink_to(sys.executable)
    settings.DJANGO_RESUME_JSON_RESUME_PYTHON = str(platform_python)
    monkeypatch.setattr(themes, "_check_cache_authority", lambda: None)
    result = themes._run_process(["true"], cwd=tmp_path, timeout=10)
    assert result.returncode == 0


@pytest.mark.parametrize("operation", ["install", "render"])
def test_bad_interpreter_fails_before_cache_work(tmp_path, settings, operation):
    target = tmp_path / "absent-cache"
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = target
    settings.DJANGO_RESUME_JSON_RESUME_PYTHON = b"/usr/bin/python3"
    with pytest.raises(
        themes.JsonResumeThemeError, match="DJANGO_RESUME_JSON_RESUME_PYTHON"
    ):
        if operation == "install":
            themes.install_catalog_theme("even", timeout=5)
        else:
            themes.render_theme(SimpleNamespace(), "jsonresume-theme-even", timeout=5)
    assert not target.exists()


def test_configured_interpreter_runs_process_in_pinned_directory(
    tmp_path, settings, monkeypatch
):
    import sys

    settings.DJANGO_RESUME_JSON_RESUME_PYTHON = sys.executable
    monkeypatch.setattr(themes.sys, "executable", "")
    monkeypatch.setattr(themes, "_check_cache_authority", lambda: None)
    result = themes._run_process(["pwd"], cwd=tmp_path, timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == str(tmp_path.resolve())


def test_cache_ancestors_need_only_search_permission(tmp_path):
    locked = tmp_path / "search-only"
    locked.mkdir()
    (locked / "cache").mkdir(mode=0o700)
    locked.chmod(0o311)
    try:
        descriptor = themes._open_directory(locked / "cache" / "new", create=True)
        themes.os.close(descriptor)
        assert (locked / "cache" / "new").is_dir()
    finally:
        locked.chmod(0o700)


def test_existing_ancestors_are_not_recreated(tmp_path, monkeypatch):
    existing = tmp_path / "existing"
    existing.mkdir()

    def denied(*args, **kwargs):
        # Mandatory access control can refuse mkdir on existing directories.
        raise PermissionError("mkdir refused")

    monkeypatch.setattr(themes.os, "mkdir", denied)
    descriptor = themes._open_directory(existing, create=True)
    themes.os.close(descriptor)
    with pytest.raises(PermissionError):
        themes._open_directory(existing / "missing", create=True)


@pytest.mark.parametrize("exit_code", [0, 7])
def test_completed_command_retires_pipe_detached_child_before_reaping(
    tmp_path, monkeypatch, exit_code
):
    import fcntl
    import os
    import signal
    import sys

    lock = tmp_path / "child.lock"
    ready = tmp_path / "ready"
    child = (
        "import fcntl,time,pathlib; "
        f"f=open({str(lock)!r},'w'); fcntl.flock(f,fcntl.LOCK_EX); "
        f"pathlib.Path({str(ready)!r}).touch(); time.sleep(2)"
    )
    script = (
        "import subprocess,sys,time,pathlib; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}], "
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        f"p=pathlib.Path({str(ready)!r}); "
        "\nwhile not p.exists(): time.sleep(.01)\n"
        f"sys.exit({exit_code})"
    )
    processes = []
    popen = themes.subprocess.Popen
    terminate = themes._terminate_process_tree
    retired_unreaped = []

    def launch(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    def retire(process):
        retired_unreaped.append(process.returncode is None)
        terminate(process)

    monkeypatch.setattr(themes.subprocess, "Popen", launch)
    monkeypatch.setattr(themes, "_terminate_process_tree", retire)
    try:
        result = themes._run_process(
            [sys.executable, "-c", script], cwd=tmp_path, timeout=5
        )
        assert result.returncode == exit_code
        assert retired_unreaped == [True]
        import time

        with lock.open() as stream:
            deadline = time.monotonic() + 1
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
    finally:
        for process in processes:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.wait()


@pytest.mark.parametrize(
    "platform,exited,allowed",
    [("darwin", True, True), ("darwin", False, False), ("linux", True, False)],
)
def test_group_permission_error_only_accepts_darwin_completed_leader(
    monkeypatch, platform, exited, allowed
):
    monkeypatch.setattr(themes.sys, "platform", platform)
    monkeypatch.setattr(themes.os, "killpg", Mock(side_effect=PermissionError))
    waitid = Mock(return_value=SimpleNamespace(si_pid=123) if exited else None)
    monkeypatch.setattr(themes.os, "waitid", waitid)
    process = SimpleNamespace(pid=123)
    if allowed:
        themes._terminate_process_tree(process)
    else:
        with pytest.raises(PermissionError):
            themes._terminate_process_tree(process)


@pytest.mark.parametrize("exited,allowed", [(True, True), (False, False)])
def test_darwin_group_permission_error_without_waitid_uses_poll(
    monkeypatch, exited, allowed
):
    # CPython before 3.13 on macOS has no os.waitid.
    monkeypatch.delattr(themes.os, "waitid", raising=False)
    monkeypatch.setattr(themes.sys, "platform", "darwin")
    monkeypatch.setattr(themes.os, "killpg", Mock(side_effect=PermissionError))
    process = SimpleNamespace(pid=123, poll=Mock(return_value=0 if exited else None))
    if allowed:
        themes._terminate_process_tree(process)
    else:
        with pytest.raises(PermissionError):
            themes._terminate_process_tree(process)
    process.poll.assert_called_once_with()


@pytest.mark.parametrize("exit_code", [0, 7])
def test_command_completion_without_waitid_retires_group(
    tmp_path, monkeypatch, exit_code
):
    import os
    import sys

    monkeypatch.delattr(themes.os, "waitid", raising=False)
    killed = []
    killpg = os.killpg

    def record(pgid, sig):
        killed.append(pgid)
        return killpg(pgid, sig)

    monkeypatch.setattr(themes.os, "killpg", record)
    monkeypatch.setattr(themes, "_check_cache_authority", lambda: None)
    result = themes._run_process(
        [sys.executable, "-c", f"print('done'); raise SystemExit({exit_code})"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == exit_code
    assert result.stdout.strip() == "done"
    assert len(killed) == 1
