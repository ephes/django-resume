from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    def register_plugins(self):
        from .timelines import TimelinePlugin
        from .plugins import plugin_registry

        plugin_registry.register(TimelinePlugin)

        print("Plugin registry: ", plugin_registry.plugins)

    def ready(self):
        self.register_plugins()
