from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    @staticmethod
    def register_plugins():
        from .timelines import FreelanceTimelinePlugin, EmployedTimelinePlugin
        from .tokens import TokenPlugin
        from .projects import ProjectsPlugin
        from .education import EducationPlugin
        from .about import AboutPlugin
        from .plugin_registry import plugin_registry

        plugin_registry.register(FreelanceTimelinePlugin)
        plugin_registry.register(EmployedTimelinePlugin)
        plugin_registry.register(EducationPlugin)
        plugin_registry.register(ProjectsPlugin)
        plugin_registry.register(AboutPlugin)
        plugin_registry.register(TokenPlugin)

    def ready(self):
        self.register_plugins()
