from django.core.management.base import BaseCommand, CommandError

from ...formats.json_resume.importer import (
    JsonResumeImportError,
    get_owner,
    import_resume_file,
)


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
        if not report.valid:
            for error in report.validation_errors:
                self.stderr.write(f"validation error: {error}")
            raise CommandError("Import failed JSON Resume schema validation.")

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
        assert result.resume is not None
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {options['input']} as resume {result.resume.slug!r}"
            )
        )
