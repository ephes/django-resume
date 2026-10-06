from django.core.management.base import BaseCommand, CommandError

from ...formats.json_resume.themes import (
    JsonResumeThemeError,
    cache_dir,
    install_catalog_themes,
)


class Command(BaseCommand):
    help = (
        "Install pinned JSON Resume catalog themes and the pinned resumed renderer "
        "into the local theme cache (npm lifecycle scripts are not run)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "keys",
            nargs="*",
            help="Catalog keys to install (default: every enabled catalog theme)",
        )

    def handle(self, *args, **options):
        try:
            entries = install_catalog_themes(options["keys"] or None)
        except JsonResumeThemeError as exc:
            raise CommandError(str(exc)) from exc
        for entry in entries:
            self.stdout.write(f"Installed {entry.package}@{entry.version}")
        self.stdout.write(f"Theme cache: {cache_dir()}")
