import sys
import importlib.util

from typing import TYPE_CHECKING

from django.db import models
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from .plugins import SimplePlugin


class ResumeManager(models.Manager["Resume"]):
    def remove_plugin_data_by_name(self, plugin_name: str) -> None:
        for resume in self.all():
            plugin_data = resume.plugin_data
            plugin_data.pop(plugin_name, None)
            assert plugin_name not in plugin_data
            resume.plugin_data = plugin_data
            resume.save()


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


class Plugin(models.Model):
    name = models.CharField(max_length=255)
    model = models.CharField(max_length=255, null=True, blank=True)
    prompt = models.TextField()
    module = models.TextField()
    form_template = models.TextField()
    content_template = models.TextField()

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def __str__(self) -> str:
        return self.name

    def to_plugin(self) -> "SimplePlugin":
        """
        Dynamically create a plugin from the model data.
        """
        spec = importlib.util.spec_from_loader(self.name, loader=None)
        module = importlib.util.module_from_spec(spec)  # type: ignore

        exec(self.module, module.__dict__)

        # Add to sys.modules so it can be imported elsewhere
        sys.modules[self.name] = module

        # Use the module
        from .plugins.base import SimpleStringTemplates

        simple_string_templates = SimpleStringTemplates(
            main=self.content_template, form=self.form_template
        )

        def set_string_templates_hook(self_plugin):
            self_plugin.templates.set_string_templates(simple_string_templates)

        [plugin_class_name] = [
            symbol
            for symbol in dir(module)
            if str(symbol).endswith("Plugin") and not str(symbol) == "SimplePlugin"
        ]
        getattr(module, plugin_class_name).init_hooks.append(set_string_templates_hook)
        plugin = getattr(module, plugin_class_name)

        return plugin
