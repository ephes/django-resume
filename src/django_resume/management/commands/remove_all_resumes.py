from django.core.management.base import BaseCommand

from ...models import Resume


class Command(BaseCommand):
    help = "Remove all resumes from the database"

    def handle(self, *args, **options):
        Resume.objects.all().delete()
