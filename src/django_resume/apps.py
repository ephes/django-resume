from django.conf import settings
from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    @staticmethod
    def register_plugins() -> None:
        from . import plugins

        plugins.plugin_registry.register_plugin_list(
            [
                plugins.FreelanceTimelinePlugin,
                plugins.EmployedTimelinePlugin,
                plugins.EducationPlugin,
                plugins.PermissionDeniedPlugin,
                plugins.ProjectsPlugin,
                plugins.AboutPlugin,
                plugins.SkillsPlugin,
                plugins.ThemePlugin,
                plugins.TokenPlugin,
                plugins.IdentityPlugin,
                plugins.CoverPlugin,
            ]
        )

    def ready(self) -> None:
        self.register_plugins()
        if getattr(settings, "DJANGO_RESUME_DB_PLUGINS", False):
            from .models import Plugin

            Plugin.objects.register_plugin_models()

            # Import signals to connect them
            from . import signals  # noqa: F401
