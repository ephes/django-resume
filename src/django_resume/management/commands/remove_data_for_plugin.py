from django.core.management.base import BaseCommand

from ...models import Resume


class Command(BaseCommand):
    help = "For a given plugin, remove all data from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "plugin_name",
            type=str,
            help="Name of the plugin for which all data should be remove",
        )

    def handle(self, *args, **options):
        plugin_name = options["plugin_name"]
        for resume in Resume.objects.all():
            plugin_data = resume.plugin_data
            plugin_data.pop(plugin_name, None)
            assert plugin_name not in plugin_data
            resume.plugin_data = plugin_data
            resume.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted all data for plugin: {plugin_name}"
            )
        )
