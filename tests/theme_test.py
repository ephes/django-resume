from django_resume.plugins.base import ThemedTemplates, get_current_theme


def test_theme_paths():
    # Given a ThemedTemplates instance
    templates = ThemedTemplates(template_names={"main": "foo.html", "form": "bar.html"})

    # When we set the plugin name and theme and get the paths
    templates.set_plugin_name_and_theme("about", "plain")
    form_template_path = templates.get_template_path("form")

    # Then the form template path should be correct
    assert form_template_path == "django_resume/plugins/about/plain/bar.html"
    assert templates.main == "django_resume/plugins/about/plain/foo.html"  # type: ignore


def test_get_theme_from_resume(resume):
    # Given a Resume with a theme
    resume.plugin_data = {"theme": {"name": "foobar"}}

    # When we get the theme from the resume
    theme = get_current_theme(resume)

    # Then the theme should be correct
    assert theme == "foobar"
