import struct
import zlib

import pytest

from django_resume.models import Resume


@pytest.fixture
def user(django_user_model):
    return django_user_model(username="testuser", password="password")


@pytest.fixture
def resume(user):
    return Resume(name="John Doe", slug="john-doe", owner=user)


@pytest.fixture
def timeline_item_data():
    return {
        "role": "Software Developer",
        "company_name": "ACME Inc.",
        "company_url": "https://example.org",
        "description": "I did some stuff",
        "start": "2020",
        "end": "2022",
        "badges": '["remote", "full-time"]',
        "position": 1,
    }


def png_bytes(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw_rows = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw_rows))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def in_memory_storage(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
