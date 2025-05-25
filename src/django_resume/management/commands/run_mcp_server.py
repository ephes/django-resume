"""Django management command to run the MCP server."""

import asyncio
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the django-resume MCP server"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default="localhost",
            help="Host to bind to (default: localhost)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="Port to bind to (default: stdio mode)",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        self.stdout.write(self.style.SUCCESS("Starting django-resume MCP server..."))

        if options["port"]:
            self.stdout.write(
                self.style.WARNING(
                    "TCP mode not yet implemented. Running in stdio mode."
                )
            )

        try:
            from django_resume.entrypoints.mcp_server_lazy import main

            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("MCP server stopped."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start MCP server: {e}"))
            raise
