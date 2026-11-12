"""The supported object pointer subset is identical at every boundary."""

import pytest

from django_resume.interchange.conflicts import detect_path_conflicts
from django_resume.interchange.coordinator import (
    PathConflictError,
    ResolvedAdapter,
    build_document,
)
from django_resume.interchange.pointer import get_pointer, set_pointer
from django_resume.interchange.protocols import AdapterExport


@pytest.mark.parametrize(
    "pointer", ["", "/", "missing/slash", "/a~1b", "/a~0b", "/a//b", "/a/"]
)
def test_invalid_pointer_is_rejected_consistently(pointer):
    for operation in (
        lambda: get_pointer({}, pointer),
        lambda: set_pointer({}, pointer, 1),
        lambda: detect_path_conflicts({pointer: ["synthetic"]}),
    ):
        with pytest.raises(ValueError):
            operation()


@pytest.mark.parametrize("declaration", ["owned_paths", "multivalued_paths"])
@pytest.mark.parametrize("pointer", ["/", "/a~1b", "missing/slash", "/a//b"])
def test_adapter_declarations_are_preflighted(pointer, declaration):
    class Adapter:
        owned_paths = ("/normal",)
        multivalued_paths = ()

        def export(self, facts):
            pytest.fail("invalid declarations must be refused before calling adapters")

    adapter = Adapter()
    setattr(adapter, declaration, (pointer,))
    with pytest.raises(PathConflictError):
        build_document([ResolvedAdapter("synthetic", adapter, {})])


def test_nested_paths_write_lookup_and_conflict_agree():
    document = {}
    set_pointer(document, "/basics/name", "Example")
    assert get_pointer(document, "/basics/name") == "Example"
    assert (
        detect_path_conflicts({"/basics": ["a"], "/basics/name": ["b"]}).kind
        == "overlap"
    )

    class Adapter:
        owned_paths = ("/basics/name",)
        multivalued_paths = ()

        def export(self, facts):
            return AdapterExport(contributions=[("/basics/name", "Example")])

    assert build_document([ResolvedAdapter("synthetic", Adapter(), {})])[0] == document
