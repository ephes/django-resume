from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, router, transaction

from ...models import Resume


class Command(BaseCommand):
    help = "Preview all resumes, or explicitly delete every owner's resumes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-all-resumes",
            action="store_true",
            help="Permanently delete every resume for every owner in this database",
        )

    def handle(self, *args, **options):
        database = router.db_for_write(Resume)
        resumes = Resume.objects.using(database)
        if not options["delete_all_resumes"]:
            count = resumes.count()
            self.stdout.write(
                f"Preview: {count} resumes across all owners. "
                "Use --delete-all-resumes to permanently delete them."
            )
            return
        try:
            with transaction.atomic(using=database):
                _, deleted_by_model = resumes.all().delete()
        except DatabaseError as exc:
            raise CommandError(
                f"Could not remove resumes; deletion rolled back: {exc}"
            ) from exc
        count = deleted_by_model.get(Resume._meta.label, 0)
        self.stdout.write(f"Deleted {count} resumes across all owners.")
