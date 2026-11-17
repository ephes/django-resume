from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._file_rollback import writer_locks
from ._path_safety import resolve_within, validate_plugin_name
from ._plugin_publication import Publication


class Command(BaseCommand):
    help = "Inspect or reconcile an interrupted filesystem plugin publication"

    def add_arguments(self, parser):
        parser.add_argument("plugin_name")
        parser.add_argument(
            "--action", choices=["status", "restore", "finish"], default="status"
        )

        parser.add_argument("--database-outcome", choices=["rolled-back", "committed"])

    def handle(self, *args, **options):
        name = validate_plugin_name(options["plugin_name"])
        paths = [
            resolve_within(Path.cwd() / "core/plugins", f"{name}.py"),
            resolve_within(
                Path.cwd() / "templates",
                f"django_resume/plugins/{name}/plain/content.html",
            ),
            resolve_within(
                Path.cwd() / "templates",
                f"django_resume/plugins/{name}/plain/form.html",
            ),
        ]
        if len(set(paths)) != 3:
            raise CommandError("Plugin targets must resolve to distinct files")
        with writer_locks(paths):
            publication = Publication(paths)
            if options["action"] == "status":
                try:
                    publication.load()
                except CommandError:
                    # Still show a bounded regular record for manual
                    # reconciliation, then report why it cannot be applied.
                    intent = publication.intent
                    if (
                        not intent.is_symlink()
                        and intent.is_file()
                        and intent.stat().st_size <= 131072
                    ):
                        self.stdout.write(intent.read_text(errors="replace"))
                    raise
                self.stdout.write(publication.intent.read_text())
                return
            publication.load()
            if publication.data["operation"] == "remove":
                expected = (
                    "rolled-back" if options["action"] == "restore" else "committed"
                )
                if options["database_outcome"] != expected:
                    raise CommandError(
                        f"Removal database outcome is unknown; verify the recorded database "
                        f"and pass --database-outcome {expected} for this action"
                    )
            try:
                publication.apply("old" if options["action"] == "restore" else "new")
                publication.retire()
            except OSError as error:
                raise CommandError(
                    f"Recovery incomplete; retain {publication.intent}: {error}"
                ) from error
            self.stdout.write("Plugin generation reconciled")
