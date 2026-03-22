from django.db import models, transaction
from django.contrib.auth import get_user_model


class ResumeManager(models.Manager["Resume"]):
    def remove_plugin_data_by_name(self, plugin_name: str) -> None:
        resumes_to_update = []
        for resume in self.only("id", "plugin_data"):
            if plugin_name not in resume.plugin_data:
                continue
            plugin_data = dict(resume.plugin_data)
            plugin_data.pop(plugin_name, None)
            assert plugin_name not in plugin_data
            resume.plugin_data = plugin_data
            resumes_to_update.append(resume)
        if resumes_to_update:
            with transaction.atomic():
                self.bulk_update(resumes_to_update, ["plugin_data"])


class Resume(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    plugin_data = models.JSONField(default=dict, blank=True, null=False)

    objects: ResumeManager = ResumeManager()

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def __str__(self) -> str:
        return self.name

    @property
    def token_is_required(self) -> bool:
        from .plugins.tokens import TokenPlugin

        return TokenPlugin.token_is_required(self.plugin_data.get(TokenPlugin.name, {}))

    @property
    def current_theme(self) -> str:
        from .plugins import plugin_registry
        from .plugins.theme import ThemePlugin

        theme_plugin = plugin_registry.get_plugin(ThemePlugin.name)
        if theme_plugin is not None:
            return theme_plugin.get_data(self).get("name", "plain")
        return "plain"

    def save(self, *args, **kwargs) -> None:
        if self.plugin_data is None:
            self.plugin_data = {}
        super().save(*args, **kwargs)
