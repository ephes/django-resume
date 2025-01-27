import sys

from django.core.management.base import BaseCommand

from ...models import Plugin
from ...plugin_generator import parse_llm_output_as_simple_plugin


class Command(BaseCommand):
    help = "Create a django-resume plugin model from stdin input"

    def handle(self, *args, **kwargs):
        self.stdout.write("Waiting for input... (Ctrl+D to end)")
        input_text = sys.stdin.read().strip()
        parsed_output = parse_llm_output_as_simple_plugin(input_text)
        plugin = Plugin(
            name=parsed_output["name"],
            prompt="forgot the prompt",
            module=parsed_output["module"],
            content_template=parsed_output["content_template"],
            form_template=parsed_output["form_template"],
        )
        plugin.save()
        print("plugin: ", plugin)
