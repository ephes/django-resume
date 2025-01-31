from django.core.management.base import BaseCommand

from ...plugin_generator import get_simple_plugin_context


class Command(BaseCommand):
    help = "Create a few-shot context for a new plugin"

    def add_arguments(self, parser):
        parser.add_argument(
            "prompt",
            type=str,
            help="The prompt to generate the few-shot context for",
        )

    def handle(self, *args, **options):
        prompt = options["prompt"]
        llm_context = get_simple_plugin_context(prompt)
        print(llm_context)
