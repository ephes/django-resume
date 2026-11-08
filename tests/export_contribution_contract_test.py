"""Synthetic adapter contract failures reach the export error boundary."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from django_resume.interchange.coordinator import (
    PathConflictError,
    ResolvedAdapter,
    build_document,
)
from django_resume.interchange.protocols import AdapterExport
from django_resume.plugins import SimplePlugin, plugin_registry


class ContributionAdapter:
    def __init__(self, pointer, values, *, multivalued=False):
        self.owned_paths = (pointer,)
        self.multivalued_paths = (pointer,) if multivalued else ()
        self.contributions = [(pointer, value) for value in values]

    def export(self, facts):
        return AdapterExport(contributions=self.contributions)


@pytest.fixture(
    params=[
        "same",
        "different",
        "string",
        "mapping",
        "null",
        "integer",
        "boolean",
        "tuple",
    ]
)
def invalid_adapter(request):
    kind = request.param
    if kind in {"same", "different"}:
        pointer = "/basics/name"
        values = [
            "private-first",
            "private-first" if kind == "same" else "private-last",
        ]
        adapter = ContributionAdapter(pointer, values)
        message = f"Adapter 'synthetic' contributed non-multivalued path {pointer!r} more than once"
    else:
        pointer = "/work"
        value = {
            "string": "private-value",
            "mapping": {"private-key": "private-value"},
            "null": None,
            "integer": 42,
            "boolean": False,
            "tuple": ({"name": "private-value"},),
        }[kind]
        adapter = ContributionAdapter(pointer, [value], multivalued=True)
        message = f"Adapter 'synthetic' must contribute a list for multivalued path {pointer!r}"
    return adapter, message


def test_invalid_contributions_are_refused_before_assembly(invalid_adapter, mocker):
    adapter, message = invalid_adapter
    assemble = mocker.patch("django_resume.interchange.coordinator.set_pointer")
    with pytest.raises(PathConflictError) as caught:
        build_document([ResolvedAdapter("synthetic", adapter, {})])
    assert str(caught.value) == message
    assemble.assert_not_called()


def test_multivalued_lists_preserve_empty_and_repeated_contributions():
    first = ContributionAdapter(
        "/work", [[], [{"name": "A"}], [{"name": "B"}]], multivalued=True
    )
    second = ContributionAdapter("/work", [[{"name": "C"}], []], multivalued=True)
    document, notes = build_document(
        [ResolvedAdapter("first", first, {}), ResolvedAdapter("second", second, {})]
    )
    assert document == {"work": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
    assert notes == []
    assert build_document(
        [
            ResolvedAdapter(
                "empty", ContributionAdapter("/work", [[]], multivalued=True), {}
            )
        ]
    ) == ({"work": []}, [])


@pytest.mark.django_db
@pytest.mark.parametrize("existing_output", [False, True])
def test_invalid_export_does_not_publish_cli_or_browser_artifacts(
    invalid_adapter, existing_output, client, user, resume, tmp_path, monkeypatch
):
    adapter, message = invalid_adapter

    class SyntheticPlugin(SimplePlugin):
        name = "synthetic"

        def get_export_adapters(self):
            return {"json_resume": adapter}

    # Keep the actual registry discovery, exporter, command and HTTP view chain.
    monkeypatch.setattr(plugin_registry, "get_all_plugins", lambda: [SyntheticPlugin()])
    user.save()
    resume.save()
    output = tmp_path / "resume.json"
    if existing_output:
        output.write_bytes(b"previous complete export\n")
    stdout = StringIO()
    with pytest.raises(CommandError) as caught:
        call_command(
            "export_json_resume",
            resume.slug,
            output=str(output),
            stdout=stdout,
            stderr=StringIO(),
        )
    assert str(caught.value) == f"Adapter configuration error: {message}"
    assert stdout.getvalue() == ""
    if existing_output:
        assert output.read_bytes() == b"previous complete export\n"
        assert list(tmp_path.iterdir()) == [output]
    else:
        assert list(tmp_path.iterdir()) == []

    client.force_login(user)
    response = client.get(
        reverse("django_resume:json-resume", kwargs={"slug": resume.slug})
    )
    assert response.status_code == 500
    assert response.content == b"Adapter configuration error"
    assert response.headers["Content-Type"].startswith("text/plain")
    assert "Content-Disposition" not in response.headers
