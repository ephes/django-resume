from django.db import migrations

LEGACY_EDUCATION_FIELDS = ("school_name", "school_url", "start", "end")


def education_to_list(apps, schema_editor):
    """Move single-entry education data into the list plugin shape."""
    Resume = apps.get_model("django_resume", "Resume")
    for resume in Resume.objects.only("id", "plugin_data").iterator():
        data = (resume.plugin_data or {}).get("education")
        if not isinstance(data, dict) or "items" in data or "flat" in data:
            continue
        if any(data.get(field) for field in LEGACY_EDUCATION_FIELDS):
            item = {field: data.get(field, "") for field in LEGACY_EDUCATION_FIELDS}
            item.update({"id": "education-1", "degree": "", "position": 0})
            new_data = {"flat": {"title": "Education"}, "items": [item]}
        else:
            new_data = {}
        resume.plugin_data["education"] = new_data
        resume.save(update_fields=["plugin_data"])


def education_to_single_entry(apps, schema_editor):
    """Keep the first entry by position; further entries cannot be represented."""
    Resume = apps.get_model("django_resume", "Resume")
    for resume in Resume.objects.only("id", "plugin_data").iterator():
        data = (resume.plugin_data or {}).get("education")
        if not isinstance(data, dict) or "items" not in data:
            continue
        items = sorted(data["items"], key=lambda item: item.get("position", 0))
        first = items[0] if items else {}
        resume.plugin_data["education"] = {
            field: first.get(field, "") for field in LEGACY_EDUCATION_FIELDS
        }
        resume.save(update_fields=["plugin_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("django_resume", "0002_resume_integration_data"),
    ]

    operations = [
        migrations.RunPython(education_to_list, education_to_single_entry),
    ]
