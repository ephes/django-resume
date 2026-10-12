from pathlib import Path

import pytest

from django_resume.entrypoints.loc import (
    _is_test_path,
    _normalized_path,
    area_for_path,
    directory_bucket_for_path,
)


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("./src/django_resume/views.py", Path("src/django_resume/views.py")),
        (Path("./tests/tokens/tokens_test.py"), Path("tests/tokens/tokens_test.py")),
        ("README.rst", Path("README.rst")),
    ],
)
def test_normalized_path_strips_dot_prefixes(raw_path, expected):
    assert _normalized_path(raw_path) == expected


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("src/django_resume/views.py", False),
        ("tests/views_test.py", True),
        ("e2e_tests/inline_test.py", True),
        ("src/django_resume/static/django_resume/js/edit.test.js", True),
        ("src/django_resume/static/django_resume/js/edit.spec.js", True),
        ("src/django_resume/test_helpers.py", True),
    ],
)
def test_is_test_path_detects_repo_test_naming_patterns(raw_path, expected):
    assert _is_test_path(Path(raw_path)) is expected


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("./src/django_resume/views.py", "src"),
        ("tests/views_test.py", "tests"),
        ("e2e_tests/inline_test.py", "tests"),
        ("src/django_resume/static/django_resume/js/edit.test.js", "tests"),
        ("README.rst", "docs"),
        ("docs/dev/develop.txt", "docs"),
        ("example/core/views.py", "example"),
        ("talk/talk.md", "talk"),
        ("images/preview.svg", "images"),
        ("pyproject.toml", "tooling"),
    ],
)
def test_area_for_path_groups_files_into_expected_repo_areas(raw_path, expected):
    assert area_for_path(raw_path) == expected


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("./src/django_resume/views.py", "src/django_resume"),
        ("tests/views_test.py", "tests"),
        ("tests/tokens/tokens_test.py", "tests/tokens"),
        ("e2e_tests/inline_test.py", "e2e_tests"),
        ("docs/dev/develop.txt", "docs/dev"),
        ("docs/changelog.txt", "docs"),
        ("example/templates/base.html", "example/templates"),
        ("talk/talk.md", "talk"),
        ("pyproject.toml", "."),
    ],
)
def test_directory_bucket_for_path_matches_expected_breakdown(raw_path, expected):
    assert directory_bucket_for_path(raw_path) == expected


@pytest.mark.parametrize("failed_call", [1, 2])
@pytest.mark.parametrize("failure", ["timeout", "missing", "permission"])
def test_cloc_failure_exits_without_report(mocker, capsys, failed_call, failure):
    import subprocess

    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value="/usr/bin/cloc")
    fallback = mocker.patch.object(loc, "_count_with_python")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 60
        assert kwargs["check"] is True
        if len(calls) == failed_call:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            if failure == "missing":
                raise FileNotFoundError("executable disappeared")
            raise PermissionError("not executable")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    mocker.patch.object(loc.subprocess, "run", side_effect=run)
    with pytest.raises(SystemExit) as exc:
        loc.count_lines_of_code()
    assert exc.value.code == 1
    assert len(calls) == failed_call
    fallback.assert_not_called()
    output = capsys.readouterr()
    assert not output.out
    assert "cloc" in output.err
    assert "Traceback" not in output.err
    assert ("timed out" if failure == "timeout" else "could not start") in output.err


def test_cloc_valid_output_preserves_summaries(mocker, capsys):
    import subprocess

    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value="/usr/bin/cloc")
    mocker.patch.object(loc, "RichConsoleModule", None)
    run = mocker.patch.object(
        loc.subprocess,
        "run",
        side_effect=[
            subprocess.CompletedProcess(
                [],
                0,
                stdout="files,language,blank,comment,code\n1,Python,2,3,7\n1,SUM,2,3,7\n",
            ),
            subprocess.CompletedProcess(
                [],
                0,
                stdout="language,filename,blank,comment,code\nPython,src/django_resume/views.py,2,3,7\n",
            ),
        ],
    )
    assert loc.count_lines_of_code() == 0
    assert run.call_count == 2
    output = capsys.readouterr()
    assert "Python" in output.out
    assert "src/django_resume" in output.out
    assert "100.0%" in output.out
    assert not output.err


def test_missing_cloc_uses_python_fallback(mocker, capsys):
    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value=None)
    fallback = mocker.patch.object(loc, "_count_with_python", return_value=0)
    run = mocker.patch.object(loc.subprocess, "run")
    assert loc.count_lines_of_code() == 0
    fallback.assert_called_once_with()
    run.assert_not_called()
    assert "using Python fallback" in capsys.readouterr().err


def test_hanging_cloc_process_is_terminated(mocker, capsys):
    import subprocess
    import sys
    import time

    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value="/fake/cloc")
    mocker.patch.object(loc, "CLOC_TIMEOUT_SECONDS", 0.1)
    real_run = subprocess.run
    completed = []

    def run(command, **kwargs):
        completed.append(command)
        return real_run([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    mocker.patch.object(loc.subprocess, "run", side_effect=run)
    started = time.monotonic()
    with pytest.raises(SystemExit) as exc:
        loc.count_lines_of_code()
    assert exc.value.code == 1
    assert time.monotonic() - started < 5
    assert len(completed) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "timed out" in output.err
