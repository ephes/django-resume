"""Portable imports must fit their own editors without losing source values."""

from copy import deepcopy

import pytest

from django_resume.formats.json_resume.importer import import_resume_document
from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.validation import validate_document
from django_resume.models import Resume
from django_resume.plugins.education import EducationItemForm, EducationPlugin
from django_resume.plugins.languages import LanguagesItemForm, LanguagesPlugin
from tests.editor_helpers import post_current_editor


@pytest.mark.django_db
@pytest.mark.parametrize(
    "section,entry,field",
    [
        ("education", {"institution": "S" * 101}, "school_name"),
        ("education", {"institution": "School", "studyType": "D" * 201}, "degree"),
        (
            "education",
            {"institution": "School", "studyType": "D" * 100, "area": "A" * 100},
            "degree",
        ),
        ("languages", {"language": "English", "fluency": "F" * 51}, "note"),
    ],
)
def test_import_rejects_oversized_editor_fields(user, section, entry, field):
    user.save()
    document = {section: [entry]}
    original = deepcopy(document)
    assert validate_document(document) == []

    result = import_resume_document(document, owner=user, slug="oversized")

    assert result.resume is None
    assert not result.report.valid
    assert any(
        f"{section}.items[0].{field}" in error
        for error in result.report.validation_errors
    )
    assert section in result.report.mapped_plugins
    assert not Resume.objects.exists()
    assert document == original


@pytest.mark.django_db
def test_boundary_import_saves_unchanged_through_editors(client, user):
    user.save()
    document = {
        "education": [{"institution": "S" * 100, "studyType": "D" * 200}],
        "languages": [{"language": "日本語", "fluency": "F" * 50}],
    }
    result = import_resume_document(document, owner=user, slug="editable")
    assert result.report.valid
    resume = result.resume
    client.force_login(user)
    for plugin, form_class in (
        (EducationPlugin(), EducationItemForm),
        (LanguagesPlugin(), LanguagesItemForm),
    ):
        [item] = plugin.get_data(resume)["items"]
        original = deepcopy(item)
        form = form_class(data=item, resume=resume, existing_items=[item])
        assert form.is_valid(), form.errors
        response = post_current_editor(
            client, plugin.inline.get_post_item_url(resume.pk), item
        )
        assert response.status_code == 200
        resume.refresh_from_db()
        assert plugin.get_data(resume)["items"] == [original]
    assert export_resume(resume).document == document
