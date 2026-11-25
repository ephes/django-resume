from pathlib import Path

import pytest

from django_resume.entrypoints.loc import (
    _aggregate_cloc_csv,
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


@pytest.mark.parametrize("failure", ["timeout", "missing", "permission"])
def test_cloc_failure_exits_without_report(mocker, capsys, failure):
    import subprocess

    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value="/usr/bin/cloc")
    fallback = mocker.patch.object(loc, "_count_with_python")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 60
        assert kwargs["check"] is True
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "missing":
            raise FileNotFoundError("executable disappeared")
        raise PermissionError("not executable")

    mocker.patch.object(loc.subprocess, "run", side_effect=run)
    with pytest.raises(SystemExit) as exc:
        loc.count_lines_of_code()
    assert exc.value.code == 1
    assert len(calls) == 1
    fallback.assert_not_called()
    output = capsys.readouterr()
    assert not output.out
    assert "cloc" in output.err
    assert "Traceback" not in output.err
    assert ("timed out" if failure == "timeout" else "could not start") in output.err


def test_cloc_report_uses_one_scan_for_all_tables(mocker, capsys):
    import subprocess

    from django_resume.entrypoints import loc

    mocker.patch.object(loc.shutil, "which", return_value="/usr/bin/cloc")
    mocker.patch.object(loc, "RichConsoleModule", None)

    def scan(command, **kwargs):
        # A file grows after the first scan.
        code = 7 if run.call_count == 1 else 11
        if "--by-file" in command:
            receipt = (
                "language,filename,blank,comment,code,cloc metadata\n"
                f"Python,./src/django_resume/views.py,2,3,{code}\n"
                "HTML,./example/index.html,1,0,2\n"
                f"SUM,,3,3,{code + 2}\n"
            )
        else:
            receipt = (
                "files,language,blank,comment,code,cloc metadata\n"
                f"1,Python,2,3,{code}\n1,HTML,1,0,2\n2,SUM,3,3,{code + 2}\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout=receipt, stderr="")

    run = mocker.patch.object(loc.subprocess, "run", side_effect=scan)
    assert loc.count_lines_of_code() == 0
    output = capsys.readouterr()
    rows = [
        [cell.strip() for cell in line.split("|")[1:-1]]
        for line in output.out.splitlines()
        if line.startswith("|")
    ]
    assert ["Python", "1", "2", "3", "7"] in rows
    assert ["HTML", "1", "1", "0", "2"] in rows
    assert ["SUM", "2", "3", "3", "9"] in rows
    assert ["src", "1", "7", "77.8%"] in rows
    assert ["example", "1", "2", "22.2%"] in rows
    assert ["src/django_resume", "1", "7"] in rows
    assert ["example", "1", "2"] in rows
    assert "cloc metadata" in output.out
    assert not output.err
    run.assert_called_once()
    assert "--exclude-lang=JSON,Markdown" in run.call_args.args[0]


def test_cloc_receipt_preserves_filename_whitespace_and_identity():
    summary, areas, directories = _aggregate_cloc_csv(
        "language,filename,blank,comment,code\n"
        'Python," tests/sample.py",0,0,1\n'
        'Python,"./tests/sample.py",0,0,2\n'
        'Python,"./src/tool_test.py ",0,0,3\n'
        'Text,"./docs/section\nname/page.txt",0,0,4\n'
        "Python,SUM,0,0,5\n"
        "SUM,,0,0,15\n"
    )

    assert directories == {
        " tests": {"files": 1, "lines": 1},
        "tests": {"files": 1, "lines": 2},
        "src/tool_test.py ": {"files": 1, "lines": 3},
        "docs/section\nname": {"files": 1, "lines": 4},
        ".": {"files": 1, "lines": 5},
    }
    assert areas == {
        "tooling": {"files": 2, "lines": 6},
        "tests": {"files": 1, "lines": 2},
        "src": {"files": 1, "lines": 3},
        "docs": {"files": 1, "lines": 4},
    }
    assert summary["rows"][-1] == {
        "language": "SUM",
        "files": 5,
        "blank": 0,
        "comment": 0,
        "code": 15,
    }


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
