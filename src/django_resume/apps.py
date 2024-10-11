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
            CoverPlugin,
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
        plugin_registry.register(CoverPlugin)

    def ready(self):
        self.register_plugins()
