from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    @staticmethod
    def register_plugins():
        from .plugins import (
            FreelanceTimelinePlugin,
            EmployedTimelinePlugin,
            TokenPlugin,
            ProjectsPlugin,
            EducationPlugin,
            AboutPlugin,
            SkillsPlugin,
            IdentityPlugin,
            plugin_registry,
        )

        plugin_registry.register(FreelanceTimelinePlugin)
        plugin_registry.register(EmployedTimelinePlugin)
        plugin_registry.register(EducationPlugin)
        plugin_registry.register(ProjectsPlugin)
        plugin_registry.register(AboutPlugin)
        plugin_registry.register(SkillsPlugin)
        plugin_registry.register(TokenPlugin)
        plugin_registry.register(IdentityPlugin)

    def ready(self):
        self.register_plugins()
