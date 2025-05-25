import sys
import importlib.util

from typing import TYPE_CHECKING

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from typing import Type
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


class PluginManager(models.Manager["Plugin"]):
    def register_plugin_models(self) -> None:
        from . import plugins

        modules_from_models = []
        for plugin_model in self.all():
            if plugin_model.is_active:
                plugin = plugin_model.to_plugin()
                modules_from_models.append(plugin)
        plugins.plugin_registry.register_db_plugin_list(modules_from_models)


class Plugin(models.Model):
    class ModelName(models.TextChoices):
        GPT4OMINI = "4o-mini", _("gpt-4o-mini")
        GPT4O = "4o", _("gpt-4o")
        GPT41 = "4.1", _("gpt-4.1")
        GPT41MINI = "4.1-mini", _("gpt-4.1-mini")
        GPTO1MINI = "o1-mini", _("gpt-o1-mini")
        GPTO1 = "o1", _("gpt-o1")
        GPTO4MINI = "o4-mini", _("gpt-o4-mini")
        HAIKU35 = "claude-3.5-haiku", _("claude-3.5-haiku")
        SONNET37 = "claude-3.7-sonnet-latest", _("claude-3.7-sonnet")
        SONNET4 = "claude-4-sonnet", _("claude-4-sonnet")

    name = models.CharField(max_length=255, unique=True)
    model = models.CharField(
        max_length=50,
        choices=ModelName.choices,
        default=ModelName.GPT4OMINI,
        blank=True,
    )
    prompt = models.TextField(default="", blank=True)
    module = models.TextField(default="", blank=True)
    form_template = models.TextField(default="", blank=True)
    content_template = models.TextField(default="", blank=True)
    plugin_data = models.JSONField(default=dict, blank=True, null=False)
    is_active = models.BooleanField(default=False)

    objects: PluginManager = PluginManager()

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def __str__(self) -> str:
        return self.name

    def to_plugin(self) -> "Type[SimplePlugin]":
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

        def set_string_templates_hook(self_plugin):
            # Create a unique SimpleStringTemplates instance for each plugin instance.
            # This closure captures the specific template content from the database model.
            simple_string_templates = SimpleStringTemplates(
                main=self.content_template, form=self.form_template
            )
            self_plugin.templates.set_string_templates(simple_string_templates)

        [plugin_class_name] = [
            symbol
            for symbol in dir(module)
            if str(symbol).endswith("Plugin") and not str(symbol) == "SimplePlugin"
        ]
        plugin_class = getattr(module, plugin_class_name)
        if not hasattr(plugin_class, "_init_hooks"):
            plugin_class._init_hooks = []
        plugin_class._init_hooks.append(set_string_templates_hook)
        plugin = getattr(module, plugin_class_name)

        return plugin
