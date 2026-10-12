from io import StringIO

import pytest
from django.core.management import call_command

from django_resume.plugin_generator import parse_llm_output_as_simple_plugin


@pytest.mark.parametrize(
    "form",
    [
        "<form><span>before---after</span></form>",
        "<form><!-- before---after --></form>",
        '<form data-value="before---after"></form>',
        '<form><script>const value = "before---after";</script></form>',
        "<form><script>const value = `before\n---\nafter`;</script></form>",
        "<form>before</form>---explanation",
    ],
)
@pytest.mark.parametrize("ending", ["", "\n---", "\n---\n"])
@pytest.mark.parametrize("consumer", ["generator", "stdin"])
def test_form_separators_survive_generation_and_installation(
    form, ending, consumer, tmp_path, monkeypatch
):
    bundle = (
        "===safe_plugin===\n===safe_plugin.py===\n# module\n"
        "===django_resume/plugins/safe_plugin/plain/content.html===\n<div></div>\n"
        "===django_resume/plugins/safe_plugin/plain/form.html===\n" + form + ending
    )
    expected = "\n" + form + ("\n" if ending else "")
    if consumer == "generator":
        assert parse_llm_output_as_simple_plugin(bundle)["form_template"] == expected
        return
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", StringIO(bundle))
    call_command("create_plugin_from_stdin")
    path = tmp_path / "templates/django_resume/plugins/safe_plugin/plain/form.html"
    assert path.read_bytes() == expected.encode("utf-8")


@pytest.mark.parametrize("ending", ["---", "---\n", "---\r\n"])
def test_response_terminator_helper(ending):
    from django_resume.plugin_generator import strip_response_terminator

    assert strip_response_terminator("<form></form>\n" + ending) == "<form></form>\n"
    assert strip_response_terminator("<form>---text</form>") == "<form>---text</form>"


@pytest.mark.parametrize("consumer", ["generator", "stdin"])
def test_marker_in_nonfinal_form_section_is_preserved(consumer, tmp_path, monkeypatch):
    form = "\n<form></form>\n---\n"
    bundle = (
        "===safe_plugin===\n"
        "===django_resume/plugins/safe_plugin/plain/form.html==="
        + form
        + "===safe_plugin.py===\n# module\n"
        "===django_resume/plugins/safe_plugin/plain/content.html===\n<div></div>"
    )
    if consumer == "generator":
        assert parse_llm_output_as_simple_plugin(bundle)["form_template"] == form
    else:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", StringIO(bundle))
        call_command("create_plugin_from_stdin")
        path = tmp_path / "templates/django_resume/plugins/safe_plugin/plain/form.html"
        assert path.read_bytes() == form.encode("utf-8")
