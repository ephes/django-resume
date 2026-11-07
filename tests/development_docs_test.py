"""Exercise contributor commands and the release guide's artifact check."""

import io
from pathlib import Path
import re
import shlex
import tarfile
import zipfile

import pytest
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def development_guide():
    return (ROOT / "docs/dev/develop.txt").read_text()


def artifact_check():
    guide = development_guide()
    match = re.search(
        r"^   \.\. code-block:: python\n\n((?:       .*\n|\n)+)", guide, re.M
    )
    assert match, "The release guide must include an executable artifact-content check"
    return "\n".join(line[7:] for line in match[1].splitlines())


def test_contributor_setup_installs_hooks():
    setup = development_guide().split("Repository Checks")[0]
    commands = re.findall(r"^    \$ (.*)$", setup, re.M)
    calls = []
    for command in commands:
        argv = shlex.split(command)
        # Inspect argv without installing tools or modifying the checkout hooks.
        if argv[0] in {"uv", "uvx"}:
            calls.append(argv)
    assert calls == [
        ["uv", "sync", "--dev"],
        ["uvx", "prek", "install"],
        ["uvx", "prek", "install-hooks"],
    ]


@pytest.mark.parametrize("broken_format", ["wheel", "sdist"])
@pytest.mark.parametrize(
    "missing",
    [
        None,
        "models.py",
        "migrations/0001_initial.py",
        "templates/django_resume/pages/plain/resume_cv.html",
    ],
)
def test_release_artifact_check(tmp_path, monkeypatch, missing, broken_format):
    required = [
        "__init__.py",
        "models.py",
        "migrations/0001_initial.py",
        "templates/django_resume/pages/plain/resume_cv.html",
    ]
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "django_resume-0.0.0-py3-none-any.whl", "w") as wheel:
        for name in required:
            if broken_format != "wheel" or name != missing:
                wheel.writestr(f"django_resume/{name}", "synthetic")
    with tarfile.open(dist / "django_resume-0.0.0.tar.gz", "w:gz") as sdist:
        for name in required:
            if broken_format != "sdist" or name != missing:
                info = tarfile.TarInfo(f"django_resume-0.0.0/src/django_resume/{name}")
                info.size = 9
                sdist.addfile(info, io.BytesIO(b"synthetic"))
    monkeypatch.chdir(tmp_path)
    if missing:
        with pytest.raises(AssertionError, match=re.escape(missing)):
            exec(artifact_check(), {})
    else:
        exec(artifact_check(), {})


def test_installation_distinguishes_minima_from_tested_environment():
    installation = (ROOT / "docs/guide/installation.txt").read_text()
    metadata = (ROOT / "pyproject.toml").read_text()
    minimum_python = re.search(r'requires-python = "(.*?)"', metadata)[1]
    django_requirement = Requirement(re.search(r'"(django>=.*?)"', metadata)[1])
    assert f"Python ``{minimum_python}``" in installation
    assert f"Django ``{django_requirement.specifier}``" in installation
    assert "not a tested compatibility matrix" in installation
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    python_version = re.search(r'UV_PYTHON: "(.*?)"', workflow)[1]
    assert f"Python {python_version}" in installation
    lock = (ROOT / "uv.lock").read_text()
    assert 'name = "django"\nversion = "6.0.8"' in lock
    assert "Django 6.0.8" in installation
    assert ":doc:`../dev/develop`" in installation
    assert ":doc:`../guide/installation`" in development_guide()
