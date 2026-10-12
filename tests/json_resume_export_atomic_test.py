import json
import os
import stat
from io import StringIO

import pytest
from django.core.management import call_command, CommandError

from django_resume.models import Resume
from django_resume.plugins.identity import IdentityPlugin


@pytest.fixture
def export_resume(user):
    user.save()
    resume = Resume.objects.create(name="Zoë 東京", slug="unicode-export", owner=user)
    IdentityPlugin().data.set_data(resume, {"name": "Zoë 東京"})
    resume.save()
    return resume


def export(output):
    call_command(
        "export_json_resume", "unicode-export", output=str(output), stderr=StringIO()
    )


@pytest.mark.django_db
@pytest.mark.parametrize("linked", [False, True])
def test_successful_export_is_complete_unicode(export_resume, tmp_path, linked):
    output = tmp_path / "resume.json"
    output.write_bytes(b"previous export")
    destination = output
    if linked:
        destination = tmp_path / "link.json"
        destination.symlink_to(output)
    export(destination)
    if linked:
        assert destination.is_symlink()
    if os.name != "nt":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert (
        json.loads(output.read_text(encoding="utf-8"))["basics"]["name"] == "Zoë 東京"
    )
    assert "東京" in output.read_text(encoding="utf-8")
    assert output.read_bytes().endswith(b"\n")
    assert set(tmp_path.iterdir()) == {output, destination}


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["write", "flush", "replace"])
@pytest.mark.parametrize("linked", [False, True])
def test_failed_export_preserves_previous_bytes(
    export_resume, tmp_path, monkeypatch, failure, linked
):
    from django_resume.management.commands import export_json_resume as command
    import builtins
    import os
    import tempfile

    output = tmp_path / "resume.json"
    previous = b"previous complete export\n\xff"
    output.write_bytes(previous)
    destination = output
    if linked:
        destination = tmp_path / "link.json"
        destination.symlink_to(output)
    real_open = builtins.open
    real_temporary = getattr(command, "NamedTemporaryFile", tempfile.NamedTemporaryFile)
    injected = []

    class FailingWriter:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def write(self, data):
            if failure == "write":
                self.handle.write(data[:5])
                injected.append(failure)
                raise OSError("injected partial write")
            return self.handle.write(data)

        def flush(self):
            injected.append(failure)
            raise OSError("injected flush")

    if failure in {"write", "flush"}:

        def failing_open(*args, **kwargs):
            return FailingWriter(real_open(*args, **kwargs))

        # Also exercise this regression against the original direct-open code.
        monkeypatch.setattr(command, "open", failing_open, raising=False)

        def failing_temporary(*args, **kwargs):
            return FailingWriter(real_temporary(*args, **kwargs))

        monkeypatch.setattr(
            command, "NamedTemporaryFile", failing_temporary, raising=False
        )
    else:

        def fail_replace(*args):
            injected.append(failure)
            raise OSError("injected replace")

        monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected"):
        export(destination)
    assert injected == [failure]
    assert output.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {output, destination}
    if linked:
        assert destination.is_symlink()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_nonregular_output_is_rejected(export_resume, tmp_path, kind):
    output = tmp_path / "destination"
    if kind == "directory":
        output.mkdir()
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs unavailable on this platform")
        os.mkfifo(output)
    before = output.stat()
    with pytest.raises(CommandError, match="regular file"):
        export(output)
    assert output.stat().st_ino == before.st_ino
    assert output.stat().st_mode == before.st_mode
    assert list(tmp_path.iterdir()) == [output]
