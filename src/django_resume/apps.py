from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    @staticmethod
    def register_pages() -> None:
        from .pages import register_builtin_pages

        register_builtin_pages()

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
        # Pages must be registered before plugins: the first plugin
        # registration imports django_resume.urls, which calls
        # page_registry.get_urls(). If pages were not yet registered, the
        # generated page routes would be empty.
        self.register_pages()
        self.register_plugins()
