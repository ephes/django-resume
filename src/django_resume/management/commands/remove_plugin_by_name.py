from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Resume


class Command(BaseCommand):
    help = "Remove plugin by name"

    def add_arguments(self, parser):
        parser.add_argument(
            "plugin_name",
            type=str,
            help="Name of the plugin for which all data should be remove",
        )

    def handle(self, *args, **options):
        plugin_name = options["plugin_name"]
        Resume.objects.remove_plugin_data_by_name(plugin_name)

        plugin_file_name = f"{plugin_name}.py"
        plugin_path = Path.cwd() / "core" / "plugins" / plugin_file_name
        plugin_path.unlink(missing_ok=True)

        content_template_path = (
            f"django_resume/plugins/{plugin_name}/plain/content.html"
        )
        real_content_template_path = Path.cwd() / "templates" / content_template_path
        real_content_template_path.unlink(missing_ok=True)

        form_template_path = f"django_resume/plugins/{plugin_name}/plain/form.html"
        real_form_template_path = Path.cwd() / "templates" / form_template_path
        real_form_template_path.unlink(missing_ok=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted all code and data for plugin: {plugin_name}"
            )
        )
