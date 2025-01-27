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

    @staticmethod
    def register_plugin_models() -> None:
        from . import plugins
        from .models import Plugin

        modules_from_models = []
        for plugin_model in Plugin.objects.all():
            plugin = plugin_model.to_plugin()
            modules_from_models.append(plugin)
        plugins.plugin_registry.register_db_plugin_list(modules_from_models)

    def ready(self) -> None:
        self.register_plugins()
        if getattr(settings, "DJANGO_RESUME_DB_PLUGINS", False):
            self.register_plugin_models()
