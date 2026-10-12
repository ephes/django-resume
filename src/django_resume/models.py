from django.db import DatabaseError, models, router, transaction
from django.contrib.auth import get_user_model


class ResumeManager(models.Manager["Resume"]):
    def remove_plugin_data_by_name(self, plugin_name: str) -> None:
        # Manager.db routes for reads. Removal writes, so honor an explicitly
        # bound alias and otherwise ask the router, with the manager's hints,
        # for the write database.
        hints = self._hints  # type: ignore[attr-defined]  # missing from stubs
        database = self._db or router.db_for_write(self.model, **hints)
        resumes = self.using(database)
        with transaction.atomic(using=database):
            for resume in resumes.select_for_update().only("id", "plugin_data"):
                original = resume.plugin_data
                if plugin_name not in original:
                    continue
                updated = dict(original)
                updated.pop(plugin_name)
                # SQLite ignores row locks. Compare the complete snapshot so
                # even an unlocked backend cannot silently replace newer data.
                changed = resumes.filter(pk=resume.pk, plugin_data=original).update(
                    plugin_data=updated
                )
                if changed != 1:
                    raise DatabaseError(
                        "Resume plugin data changed during removal; retry the operation."
                    )


class Resume(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    plugin_data = models.JSONField(default=dict, blank=True, null=False)
    integration_data = models.JSONField(default=dict, blank=True, null=False)

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

    @staticmethod
    def language_from_plugin_data(plugin_data: dict) -> str:
        """The resume language stored with the page theme, if it is configured."""
        from .i18n import normalize_language

        theme_data = plugin_data.get("theme") or {}
        if not isinstance(theme_data, dict):
            return ""
        return normalize_language(theme_data.get("language"))

    @property
    def language(self) -> str:
        """The language the resume's pages render in; empty means the active
        site language."""
        return self.language_from_plugin_data(self.plugin_data or {})

    def save(self, *args, **kwargs) -> None:
        if self.plugin_data is None:
            self.plugin_data = {}
        if self.integration_data is None:
            self.integration_data = {}
        super().save(*args, **kwargs)
