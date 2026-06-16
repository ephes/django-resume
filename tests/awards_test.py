def test_awards_item_form_valid_and_context(resume):
    from django_resume.plugins.awards import AwardsItemForm

    form = AwardsItemForm(
        data={
            "id": "a1",
            "title": "ADC Germany 2024: Two Bronze awards",
            "project": "Project: Tomy Saurk",
            "year": "2024",
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )
    assert form.is_valid(), form.errors
    ctx = form.set_context(form.cleaned_data, {"edit_url": "#", "delete_url": "#"})
    assert ctx["award"]["title"].startswith("ADC Germany 2024")
    assert ctx["award"]["year"] == "2024"


def test_awards_plugin_registered():
    from django_resume.plugins import plugin_registry

    assert plugin_registry.get_plugin("awards") is not None
