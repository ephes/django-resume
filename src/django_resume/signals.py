from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from .models import Plugin


@receiver(post_save, sender=Plugin)
def reload_plugins_on_save(sender, instance, created, **kwargs):
    """
    Reload the plugin registry when a Plugin model is saved.
    This handles both new plugin creation and is_active field changes.
    """
    # Skip if auto-reload is disabled (e.g., during tests)
    if getattr(settings, "DJANGO_RESUME_DISABLE_AUTO_RELOAD", False):
        return

    # Only reload if DB plugins are enabled
    if getattr(settings, "DJANGO_RESUME_DB_PLUGINS", False):
        from .plugins import plugin_registry

        plugin_registry.reload_db_plugins()


@receiver(post_delete, sender=Plugin)
def reload_plugins_on_delete(sender, instance, **kwargs):
    """
    Reload the plugin registry when a Plugin model is deleted.
    """
    # Skip if auto-reload is disabled (e.g., during tests)
    if getattr(settings, "DJANGO_RESUME_DISABLE_AUTO_RELOAD", False):
        return

    # Only reload if DB plugins are enabled
    if getattr(settings, "DJANGO_RESUME_DB_PLUGINS", False):
        from .plugins import plugin_registry

        plugin_registry.reload_db_plugins()
