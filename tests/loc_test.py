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
