"""Synthetic import boundary regressions."""

import io
import json
import os
import stat
import subprocess
import sys
import tracemalloc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from django_resume.formats.json_resume import importer
from django_resume.formats.json_resume.export import export_resume
from django_resume.models import Resume


def nested_document(depth):
    extension = []
    for _ in range(depth - 3):
        extension = [extension]
    return {"meta": {"vendor": extension}}


def deep_bytes():
    return b'{"meta":{"vendor":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}}"


def test_depth_check_extra_memory_is_independent_of_extension_width():
    narrow = {"meta": {"vendor": [{}]}}
    wide = {"meta": {"vendor": [{} for _ in range(50_000)]}}

    def peak_extra_bytes(document):
        tracemalloc.start()
        try:
            importer._check_nesting_depth(document)
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    assert peak_extra_bytes(wide) <= peak_extra_bytes(narrow) + 64 * 1024


def test_prepare_rejects_depth_before_recursive_work():
    with pytest.raises(importer.JsonResumeImportError, match="nesting depth"):
        importer.prepare_resume_import(nested_document(65), slug="deep")


def test_prepare_normalizes_recursion_exhaustion():
    with patch.object(importer, "drop_empty_dates", side_effect=RecursionError):
        with pytest.raises(importer.JsonResumeImportError, match="nesting"):
            importer.prepare_resume_import({}, slug="recursion")


def test_decoder_normalizes_recursion_exhaustion():
    with patch.object(importer.json, "loads", side_effect=RecursionError):
        with pytest.raises(importer.JsonResumeImportError, match="nesting"):
            importer.load_document_bytes(b"{}")


@pytest.mark.django_db
def test_supported_extension_round_trips(django_user_model):
    owner = django_user_model.objects.create_user(username="synthetic")
    document = nested_document(64)
    result = importer.import_resume_document(document, owner=owner, slug="supported")
    assert export_resume(result.resume).document == document


@pytest.mark.django_db
def test_deep_extension_view_creates_nothing(client, django_user_model):
    owner = django_user_model.objects.create_user(username="synthetic")
    client.force_login(owner)
    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": SimpleUploadedFile(
                "synthetic.json", deep_bytes(), "application/json"
            ),
            "slug": "deep",
            "action": "preview",
        },
    )
    assert response.status_code == 200
    assert "nesting" in str(response.context["import_form"].errors)
    assert not Resume.objects.exists()


@pytest.mark.django_db
def test_deep_extension_cli_creates_nothing(django_user_model, tmp_path):
    owner = django_user_model.objects.create_user(username="synthetic")
    path = tmp_path / "synthetic.json"
    path.write_bytes(deep_bytes())
    with pytest.raises(CommandError, match="nesting"):
        call_command("import_json_resume", str(path), owner=owner.username, slug="deep")
    assert not Resume.objects.exists()


class ReadInterleaving:
    def __init__(self, stream, change):
        self.stream = stream
        self.change = change

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def read(self, size):
        if self.change is None:
            return self.stream.read(size)
        prefix = self.stream.read(len(b'{"basics":{"name":"Alpha",'))
        change, self.change = self.change, None
        change()
        return prefix + self.stream.read(size - len(prefix))

    def seek(self, offset):
        return self.stream.seek(offset)


@pytest.mark.django_db
@pytest.mark.parametrize("restore_mtime", [False, True])
def test_same_size_rewrite_during_file_read_refuses_import(
    django_user_model, tmp_path, monkeypatch, restore_mtime
):
    owner = django_user_model.objects.create_user(username="synthetic")
    path = tmp_path / "synthetic.json"
    original = b'{"basics":{"name":"Alpha","label":"old"}}'
    rewritten = b'{"basics":{"name":"Bravo","label":"new"}}'
    assert len(original) == len(rewritten)
    path.write_bytes(original)
    before = path.stat()
    fdopen = os.fdopen

    def rewrite():
        path.write_bytes(rewritten)
        mtime = before.st_mtime_ns if restore_mtime else before.st_mtime_ns - 10**9
        os.utime(path, ns=(before.st_atime_ns, mtime))

    monkeypatch.setattr(
        os, "fdopen", lambda fd, mode: ReadInterleaving(fdopen(fd, mode, 0), rewrite)
    )
    with pytest.raises(CommandError, match="input changed during read"):
        call_command(
            "import_json_resume", str(path), owner=owner.username, slug="rewritten"
        )
    assert not Resume.objects.exists()


def test_path_replacement_preserves_open_file_generation(tmp_path, monkeypatch):
    path = tmp_path / "original.json"
    path.write_bytes(b'{"basics":{"name":"Original"}}')
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(b'{"basics":{"name":"Replacement"}}')
    fdopen = os.fdopen

    monkeypatch.setattr(
        os,
        "fdopen",
        lambda fd, mode: ReadInterleaving(
            fdopen(fd, mode, 0), lambda: replacement.replace(path)
        ),
    )
    assert importer.load_document(path) == {"basics": {"name": "Original"}}


def test_file_read_is_bounded_even_when_stat_understates_size(tmp_path):
    path = tmp_path / "growing.json"
    path.write_bytes(b"{}")
    stream = io.BytesIO(b" " * (importer.MAX_INPUT_BYTES + 100))

    def opened_stream(fd, *args, **kwargs):
        os.close(fd)
        return stream

    with (
        patch(
            "os.fstat", return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_size=2)
        ),
        patch("os.fdopen", side_effect=opened_stream),
        patch.object(stream, "read", wraps=stream.read) as read,
    ):
        with pytest.raises(importer.JsonResumeImportError, match="maximum size"):
            importer.load_document(path)
        read.assert_called_once_with(importer.MAX_INPUT_BYTES + 1)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are unavailable")
def test_fifo_fails_promptly(tmp_path):
    path = tmp_path / "input.fifo"
    os.mkfifo(path)
    script = """
import django, sys
django.setup()
from django_resume.formats.json_resume.importer import load_document, JsonResumeImportError
try:
    load_document(sys.argv[1])
except JsonResumeImportError as exc:
    assert 'regular file' in str(exc)
else:
    raise AssertionError('FIFO accepted')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "tests.settings"},
        cwd=Path(__file__).resolve().parents[1],
        timeout=20,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_file_utf8_and_directory(tmp_path):
    path = tmp_path / "valid.json"
    path.write_text(json.dumps({"vendor": "ä"}), encoding="utf-8")
    assert importer.load_document(path) == {"vendor": "ä"}
    with pytest.raises(importer.JsonResumeImportError, match="Could not read"):
        importer.load_document(tmp_path)


def test_file_open_without_unix_flags_uses_binary_mode(tmp_path, monkeypatch):
    path = tmp_path / "windows.json"
    path.write_bytes(b'{"meta":{"vendor":"\\u001a"}}\r\n')
    monkeypatch.delattr(os, "O_NONBLOCK", raising=False)
    binary_flag = 1 << 29
    monkeypatch.setattr(os, "O_BINARY", binary_flag, raising=False)
    original_open = os.open

    def platform_open(path, flags):
        return original_open(path, flags & ~binary_flag)

    with patch.object(os, "open", side_effect=platform_open) as opened:
        assert importer.load_document(path) == {"meta": {"vendor": "\x1a"}}
    opened.assert_called_once_with(path, os.O_RDONLY | os.O_BINARY)
