from contextlib import suppress

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...formats.json_resume.importer import (
    JsonResumeImportError,
    get_owner,
    import_resume_file,
)
from ...interchange.report import ImportReport


class Command(BaseCommand):
    help = "Import a JSON Resume v1.0.0 document into a new resume."

    def add_arguments(self, parser):
        parser.add_argument("input", type=str, help="JSON Resume file to import")
        parser.add_argument(
            "--owner",
            required=True,
            help="Username for the owner of the created resume",
        )
        parser.add_argument(
            "--slug",
            required=True,
            help="Slug for the created resume; must not already exist",
        )
        parser.add_argument(
            "--name",
            default=None,
            help="Resume name; defaults to basics.name or the slug",
        )
        parser.add_argument(
            "--portable-only",
            action="store_true",
            help=(
                "Ignore meta.django_resume.plugin_data and import only portable "
                "JSON Resume fields"
            ),
        )

    def handle(self, *args, **options):
        try:
            owner = get_owner(options["owner"])
            result = import_resume_file(
                options["input"],
                owner=owner,
                slug=options["slug"],
                name=options["name"],
                restore_django_resume_data=not options["portable_only"],
            )
        except JsonResumeImportError as exc:
            raise CommandError(str(exc))

        report = result.report
        # Python uses None for a standard stream with a closed descriptor at startup.
        if getattr(self.stderr, "_out", self.stderr) is not None:
            with suppress(OSError, ValueError):
                self._write_report(report)
        if not report.valid:
            raise CommandError("Import failed JSON Resume schema validation.")

        assert result.resume is not None
        slug = result.resume.slug
        try:
            if getattr(self.stdout, "_out", self.stdout) is None:
                raise OSError("stdout is unavailable")
            self.stdout.write(
                self.style.SUCCESS(f"Imported {options['input']} as resume {slug!r}")
            )
            self.stdout.flush()
        except (OSError, ValueError) as exc:
            connection = transaction.get_connection(result.resume._state.db)
            # commit_on_exit is False when the outer atomic block was entered
            # with autocommit already disabled by the caller.
            if connection.in_atomic_block and connection.commit_on_exit:
                # An outer atomic block still decides whether the resume persists.
                raise CommandError(
                    f"Resume {slug!r} was saved in the open outer transaction, but "
                    "writing the import receipt to stdout failed; it persists only "
                    "if that transaction commits."
                ) from exc
            if not connection.get_autocommit():
                # Some backends commit the importer's savepoint when no
                # transaction was open yet, so the outcome is the caller's to check.
                raise CommandError(
                    f"Resume {slug!r} was saved with autocommit disabled, but "
                    "writing the import receipt to stdout failed; check whether "
                    "your transaction committed it before retrying."
                ) from exc
            raise CommandError(
                f"Resume {slug!r} was created, but writing the import receipt "
                "to stdout failed."
            ) from exc

    def _write_report(self, report: ImportReport) -> None:
        if not report.valid:
            for error in report.validation_errors:
                self.stderr.write(f"validation error: {error}")
            return

        self.stderr.write(
            f"Mapped plugins: {', '.join(report.mapped_plugins) or '(none)'}"
        )
        self.stderr.write(
            f"Restored plugins: {', '.join(report.restored_plugins) or '(none)'}"
        )
        omitted = (
            ", ".join(
                f"{name} ({reason})" for name, reason in report.omitted_plugins.items()
            )
            or "(none)"
        )
        self.stderr.write(f"Omitted plugins: {omitted}")
        for note in report.notes:
            self.stderr.write(f"note: {note}")
