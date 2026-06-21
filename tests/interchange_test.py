import pytest

from django_resume.interchange.pointer import set_pointer


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
