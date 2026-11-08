from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

LEGACY_EDUCATION_FIELDS = ("school_name", "school_url", "start", "end")


def education_to_list(apps, schema_editor):
    """Move single-entry education data into the list plugin shape."""
    Resume = apps.get_model("django_resume", "Resume")
    alias = schema_editor.connection.alias
    rows = Resume.objects.using(alias).only("id", "plugin_data")
    for resume in rows.iterator():
        data = (resume.plugin_data or {}).get("education")
        if (
            isinstance(data, dict)
            and "items" not in data
            and "flat" not in data
            and _has_extra_values(data, LEGACY_EDUCATION_FIELDS)
        ):
            raise RuntimeError(
                "Education upgrade contains unsupported extension values. Make a database "
                "backup and export all education plugin_data before explicitly converting it."
            )
    for resume in rows.iterator():
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
        resume.save(using=alias, update_fields=["plugin_data"])


def _has_extra_values(data, allowed):
    return any(
        key not in allowed and value not in (None, "") for key, value in data.items()
    )


def _reverse_is_lossless(data):
    items = data["items"]
    flat = data.get("flat", {})
    if not isinstance(items, list) or len(items) > 1 or not isinstance(flat, dict):
        return False
    if _has_extra_values(data, {"items", "flat"}):
        return False
    if flat.get("title") not in (None, "", "Education") or _has_extra_values(
        flat, {"title"}
    ):
        return False
    return all(
        isinstance(item, dict)
        and not _has_extra_values(item, {*LEGACY_EDUCATION_FIELDS, "id", "position"})
        for item in items
    )


def education_to_single_entry(apps, schema_editor):
    """Refuse rollback before writing if legacy education cannot hold the data."""
    Resume = apps.get_model("django_resume", "Resume")
    alias = schema_editor.connection.alias
    rows = Resume.objects.using(alias).only("id", "plugin_data")
    for resume in rows.iterator():
        data = (resume.plugin_data or {}).get("education")
        if (
            isinstance(data, dict)
            and "items" in data
            and not _reverse_is_lossless(data)
        ):
            raise IrreversibleError(
                "Education rollback would lose data. Make a database backup and export "
                "all education plugin_data before explicitly converting it to the legacy shape."
            )
    for resume in rows.iterator():
        data = (resume.plugin_data or {}).get("education")
        if not isinstance(data, dict) or "items" not in data:
            continue
        first = data["items"][0] if data["items"] else {}
        resume.plugin_data["education"] = {
            field: first.get(field, "") for field in LEGACY_EDUCATION_FIELDS
        }
        resume.save(using=alias, update_fields=["plugin_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("django_resume", "0002_resume_integration_data"),
    ]

    operations = [
        migrations.RunPython(education_to_list, education_to_single_entry),
    ]
