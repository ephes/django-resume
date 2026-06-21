import pytest

from django_resume.interchange.pointer import set_pointer
from django_resume.interchange.protocols import AdapterExport
from django_resume.interchange.coordinator import (
    ResolvedAdapter,
    PathConflictError,
    build_document,
)


def test_set_pointer_creates_nested_objects():
    doc: dict = {}
    set_pointer(doc, "/basics/name", "Jane")
    set_pointer(doc, "/basics/email", "jane@example.com")
    assert doc == {"basics": {"name": "Jane", "email": "jane@example.com"}}


def test_set_pointer_sets_list_value_whole():
    doc: dict = {}
    set_pointer(doc, "/skills", [{"name": "Python"}])
    assert doc == {"skills": [{"name": "Python"}]}


def test_set_pointer_rejects_relative_pointer():
    with pytest.raises(ValueError):
        set_pointer({}, "basics/name", "x")


class _Adapter:
    def __init__(self, owned, multivalued, contributions, notes=None):
        self.owned_paths = owned
        self.multivalued_paths = multivalued
        self._contributions = contributions
        self._notes = notes or []

    def export(self, facts):
        return AdapterExport(contributions=self._contributions, notes=self._notes)


def _resolved(name, adapter):
    return ResolvedAdapter(plugin_name=name, adapter=adapter, facts={})


def test_build_document_merges_disjoint_basics_pointers():
    identity = _Adapter(("/basics/name",), (), [("/basics/name", "Jane")])
    about = _Adapter(("/basics/summary",), (), [("/basics/summary", "Hi")])
    doc, notes = build_document([_resolved("identity", identity), _resolved("about", about)])
    assert doc == {"basics": {"name": "Jane", "summary": "Hi"}}
    assert notes == []


def test_build_document_concatenates_multivalued_array():
    free = _Adapter(("/work",), ("/work",), [("/work", [{"name": "A"}])])
    emp = _Adapter(("/work",), ("/work",), [("/work", [{"name": "B"}])])
    doc, _ = build_document([_resolved("freelance", free), _resolved("employed", emp)])
    assert doc == {"work": [{"name": "A"}, {"name": "B"}]}


def test_build_document_collects_notes():
    a = _Adapter(("/skills",), (), [("/skills", [{"name": "Py"}])], notes=["dropped x"])
    _, notes = build_document([_resolved("skills", a)])
    assert notes == ["dropped x"]


def test_build_document_raises_on_scalar_path_conflict():
    a = _Adapter(("/basics/name",), (), [("/basics/name", "A")])
    b = _Adapter(("/basics/name",), (), [("/basics/name", "B")])
    with pytest.raises(PathConflictError):
        build_document([_resolved("a", a), _resolved("b", b)])


def test_build_document_raises_on_ancestor_path_overlap():
    parent = _Adapter(("/basics",), (), [("/basics", {"name": "A"})])
    child = _Adapter(("/basics/name",), (), [("/basics/name", "B")])
    with pytest.raises(PathConflictError):
        build_document([_resolved("parent", parent), _resolved("child", child)])


def test_build_document_raises_on_undeclared_contribution():
    rogue = _Adapter(("/skills",), (), [("/awards", [{"title": "X"}])])
    with pytest.raises(PathConflictError):
        build_document([_resolved("rogue", rogue)])
