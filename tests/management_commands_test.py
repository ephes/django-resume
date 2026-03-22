from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_resume.models import Resume


def test_create_plugin_from_stdin_rejects_unsafe_plugin_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "\n".join(
                [
                    "===../../escape===",
                    "===../../escape.py===",
                    "print('escape')",
                    "===django_resume/plugins/../../escape/plain/content.html===",
                    "<div>escape</div>",
                    "===django_resume/plugins/../../escape/plain/form.html===",
                    "<form></form>",
                ]
            )
        ),
    )

    with pytest.raises(CommandError, match="Invalid plugin name"):
        call_command("create_plugin_from_stdin")

    assert not (tmp_path / "escape.py").exists()


def test_create_plugin_from_stdin_creates_files_for_valid_plugin_name(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    plugin_name = "safe_plugin"
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "\n".join(
                [
                    f"==={plugin_name}===",
                    f"==={plugin_name}.py===",
                    "print('safe')",
                    f"===django_resume/plugins/{plugin_name}/plain/content.html===",
                    "<div>safe</div>",
                    f"===django_resume/plugins/{plugin_name}/plain/form.html===",
                    "<form></form>",
                ]
            )
        ),
    )

    call_command("create_plugin_from_stdin")

    assert (
        tmp_path / "core" / "plugins" / f"{plugin_name}.py"
    ).read_text().strip() == "print('safe')"
    assert (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "content.html"
    ).read_text().strip() == "<div>safe</div>"


@pytest.mark.django_db
def test_remove_plugin_by_name_rejects_unsafe_plugin_name(tmp_path, monkeypatch, user):
    monkeypatch.chdir(tmp_path)
    user.save()
    Resume.objects.create(
        name="Test Resume",
        slug="test-resume",
        owner=user,
        plugin_data={"safe_plugin": {"title": "Safe"}},
    )
    outside_file = tmp_path / "keep.txt"
    outside_file.write_text("keep")

    with pytest.raises(CommandError, match="Invalid plugin name"):
        call_command("remove_plugin_by_name", "../../keep")

    assert outside_file.read_text() == "keep"
    assert Resume.objects.get(slug="test-resume").plugin_data == {
        "safe_plugin": {"title": "Safe"}
    }


@pytest.mark.django_db
def test_remove_plugin_by_name_removes_plugin_files_and_resume_data(
    tmp_path, monkeypatch, user
):
    monkeypatch.chdir(tmp_path)
    user.save()
    plugin_name = "safe_plugin"
    Resume.objects.create(
        name="Test Resume",
        slug="test-resume",
        owner=user,
        plugin_data={plugin_name: {"title": "Safe"}, "about": {"title": "About"}},
    )
    plugin_file = tmp_path / "core" / "plugins" / f"{plugin_name}.py"
    content_template = (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "content.html"
    )
    form_template = (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "form.html"
    )
    plugin_file.parent.mkdir(parents=True, exist_ok=True)
    content_template.parent.mkdir(parents=True, exist_ok=True)
    plugin_file.write_text("print('safe')")
    content_template.write_text("<div>safe</div>")
    form_template.write_text("<form></form>")

    call_command("remove_plugin_by_name", plugin_name)

    assert not plugin_file.exists()
    assert not content_template.exists()
    assert not form_template.exists()
    assert Resume.objects.get(slug="test-resume").plugin_data == {
        "about": {"title": "About"}
    }
