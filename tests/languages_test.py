def test_languages_item_form_builds_context(resume):
    from django_resume.plugins.languages import LanguagesItemForm

    form = LanguagesItemForm(
        data={"id": "l1", "name": "Deutsch", "level": 100, "position": 0},
        resume=resume,
        existing_items=[],
    )
    assert form.is_valid(), form.errors
    ctx = form.set_context(form.cleaned_data, {"edit_url": "#", "delete_url": "#"})
    assert ctx["language"]["name"] == "Deutsch"
    assert ctx["language"]["level"] == 100


def test_languages_level_out_of_range_invalid(resume):
    from django_resume.plugins.languages import LanguagesItemForm

    form = LanguagesItemForm(
        data={"id": "l2", "name": "Englisch", "level": 250, "position": 1},
        resume=resume,
        existing_items=[],
    )
    assert not form.is_valid()  # level > 100 (max_value=100)


def test_languages_plugin_registered():
    from django_resume.plugins import plugin_registry

    assert plugin_registry.get_plugin("languages") is not None
