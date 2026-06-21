import json

from django.core.management.base import BaseCommand, CommandError

from ...formats.json_resume.export import export_resume
from ...interchange.coordinator import PathConflictError
from ...models import Resume


class Command(BaseCommand):
    help = "Export a resume to a JSON Resume v1.0.0 document."

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str, help="Slug of the resume to export")
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write JSON to this file instead of stdout",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        try:
            resume = Resume.objects.get(slug=slug)
        except Resume.DoesNotExist:
            raise CommandError(f"No resume found with slug {slug!r}")

        try:
            result = export_resume(resume)
        except PathConflictError as exc:
            raise CommandError(f"Adapter configuration error: {exc}")

        report = result.report
        self.stderr.write(
            f"Mapped plugins: {', '.join(report.mapped_plugins) or '(none)'}"
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

        if not report.valid:
            for error in report.validation_errors:
                self.stderr.write(f"validation error: {error}")
            raise CommandError(
                "Export failed JSON Resume schema validation; no output written."
            )

        payload = json.dumps(result.document, indent=2, ensure_ascii=False)
        output = options["output"]
        if output:
            with open(output, "w", encoding="utf-8") as handle:
                handle.write(payload + "\n")
            self.stderr.write(self.style.SUCCESS(f"Wrote {output}"))
        else:
            self.stdout.write(payload)
