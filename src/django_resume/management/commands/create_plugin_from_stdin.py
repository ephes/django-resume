import sys
import re

from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a django-resume plugin from stdin input"

    def handle(self, *args, **kwargs):
        self.stdout.write("Waiting for input... (Ctrl+D to end)")
        input_text = sys.stdin.read().strip()

        if not input_text:
            self.stdout.write(self.style.ERROR("No input provided"))
            return

        sections = re.split(r"===([^=]+)===", input_text.strip())
        if len(sections) < 3:
            self.stdout.write(self.style.ERROR("Invalid input format"))
            return

        plugin_name = sections[1].strip()
        plugin_data = dict(zip(sections[3::2], sections[4::2]))
        print("plugin_name: ", plugin_name)
        print("plugin_data: ", plugin_data)
        plugin_file_name = f"{plugin_name}.py"
        plugin_source = plugin_data[plugin_file_name]
        plugin_path = Path.cwd() / "core" / "plugins" / plugin_file_name
        plugin_path.parent.mkdir(parents=True, exist_ok=True)
        plugin_path.write_text(plugin_source)

        # content template
        content_template_path = (
            f"django_resume/plugins/{plugin_name}/plain/content.html"
        )
        content_template_source = plugin_data[content_template_path]

        real_content_template_path = Path.cwd() / "templates" / content_template_path
        real_content_template_path.parent.mkdir(parents=True, exist_ok=True)
        real_content_template_path.write_text(content_template_source)

        # form template
        form_template_path = f"django_resume/plugins/{plugin_name}/plain/form.html"
        form_template_source = plugin_data[form_template_path]
        form_template_source = form_template_source.split("---")[0]

        real_form_template_path = Path.cwd() / "templates" / form_template_path
        real_form_template_path.parent.mkdir(parents=True, exist_ok=True)
        real_form_template_path.write_text(form_template_source)
