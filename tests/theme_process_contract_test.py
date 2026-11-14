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
    killed = Mock()
    monkeypatch.setattr(themes, "_terminate_process_tree", killed)
    monkeypatch.setattr(themes.subprocess, "Popen", Mock(return_value=process))
    with pytest.raises(themes.JsonResumeThemeError, match="read") as error:
        themes._run_process(["synthetic"], cwd=tmp_path, timeout=1)
    assert "sensitive" not in str(error.value)
    assert killed.called
    assert process.wait.called
    assert process.stdout.closed and process.stderr.closed
