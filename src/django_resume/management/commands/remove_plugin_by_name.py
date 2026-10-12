from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction

from ...models import Resume
from ._file_rollback import backup_files
from ._path_safety import resolve_within, validate_plugin_name


class Command(BaseCommand):
    help = "Remove a filesystem plugin and its stored resume data by name"

    def add_arguments(self, parser):
        parser.add_argument(
            "plugin_name",
            type=str,
            help="Name of the plugin for which all data should be removed",
        )

    def handle(self, *args, **options):
        plugin_name = validate_plugin_name(options["plugin_name"])
        paths = [
            resolve_within(Path.cwd() / "core/plugins", f"{plugin_name}.py"),
            resolve_within(
                Path.cwd() / "templates",
                f"django_resume/plugins/{plugin_name}/plain/content.html",
            ),
            resolve_within(
                Path.cwd() / "templates",
                f"django_resume/plugins/{plugin_name}/plain/form.html",
            ),
        ]
        if len(set(paths)) != len(paths):
            raise CommandError("Plugin targets must resolve to distinct files")
        try:
            with backup_files(paths):
                with transaction.atomic():
                    for path in paths:
                        path.unlink(missing_ok=True)
                    Resume.objects.remove_plugin_data_by_name(plugin_name)
        except (OSError, DatabaseError) as error:
            raise CommandError(f"Could not remove plugin: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted all code and data for plugin: {plugin_name}"
            )
        )
