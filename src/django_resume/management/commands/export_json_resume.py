import json
import os
from contextlib import nullcontext, suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand, CommandError

from ...formats.json_resume.export import export_resume
from ...interchange.coordinator import PathConflictError
from ...interchange.report import ExportReport
from ...models import Resume
from ._plugin_publication import sync_directory


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
        output = options["output"]
        if output and report.valid:
            payload = json.dumps(result.document, indent=2, ensure_ascii=False)
            self._publish_file(output, payload)

        # File exports have their own outcome even if stderr is unavailable.
        # A CLI started with fd 2 closed has sys.stderr set to None.
        stderr_missing = getattr(self.stderr, "_out", self.stderr) is None
        if not (output and stderr_missing):
            with suppress(OSError, ValueError) if output else nullcontext():
                self._write_report(report)
                if output and report.valid:
                    self.stderr.write(self.style.SUCCESS(f"Wrote {output}"))

        if not report.valid:
            raise CommandError(
                "Export failed JSON Resume schema validation; no output written."
            )
        if not output:
            self.stdout.write(json.dumps(result.document, indent=2, ensure_ascii=False))

    def _write_report(self, report: ExportReport) -> None:
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

    @staticmethod
    def _publish_file(output: str, payload: str) -> None:
        destination = Path(output).resolve()
        if destination.exists() and not destination.is_file():
            raise CommandError("--output must name a regular file.")
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            # The temporary name is gone now; skip cleanup so a later failure
            # cannot mask the durability error below.
            temporary = None
            try:
                sync_directory(destination.parent)
            except OSError as exc:
                raise CommandError(
                    f"Export is visible at {output!r}, but publication durability "
                    "is uncertain; inspect the file before retrying."
                ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
