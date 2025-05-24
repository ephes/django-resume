import pytest
from django.test import override_settings

from django_resume.models import Plugin
from django_resume.plugins import plugin_registry

# Import signals to ensure they're connected
from django_resume import signals  # noqa: F401


@pytest.fixture(autouse=True)
def clean_plugin_registry():
    """Clean the plugin registry before and after each test."""
    # Clean before test
    plugin_registry.clear_db_plugins()
    yield
    # Clean after test
    plugin_registry.clear_db_plugins()


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_plugin_registry_reloads_on_is_active_change():
    """Test that the plugin registry reload mechanism works correctly."""

    # Create a plugin with is_active=False
    plugin = Plugin.objects.create(
        name="test_plugin",
        module="""
from django_resume.plugins import SimplePlugin

class TestActivePlugin(SimplePlugin):
    name = "test_plugin"
""",
        is_active=False,
    )

    # Manually trigger reload (since signals are disabled in tests)
    plugin_registry.reload_db_plugins()

    # Verify plugin is not in registry initially (since is_active=False)
    assert plugin.name not in plugin_registry.db_plugins

    # Change is_active to True
    plugin.is_active = True
    plugin.save()

    # Manually trigger reload
    plugin_registry.reload_db_plugins()

    # Verify plugin is now in registry
    assert plugin.name in plugin_registry.db_plugins

    # Change is_active back to False
    plugin.is_active = False
    plugin.save()

    # Manually trigger reload
    plugin_registry.reload_db_plugins()

    # Verify plugin is removed from registry
    assert plugin.name not in plugin_registry.db_plugins


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_manual_plugin_registration():
    """Test that manual plugin registration works to verify the basic functionality."""

    # Create an active plugin
    plugin = Plugin.objects.create(
        name="test_manual_plugin",
        module="""
from django_resume.plugins import SimplePlugin

class TestManualPlugin(SimplePlugin):
    name = "test_manual_plugin"
""",
        is_active=True,
    )

    # Manually trigger reload
    plugin_registry.reload_db_plugins()

    # Verify plugin is in registry
    assert plugin.name in plugin_registry.db_plugins


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_plugin_registry_reloads_on_delete():
    """Test that the plugin registry reload mechanism works when a plugin is deleted."""

    import sys

    # Create an active plugin
    plugin = Plugin.objects.create(
        name="test_plugin_delete",
        module="""
from django_resume.plugins import SimplePlugin

class TestDeletePlugin(SimplePlugin):
    name = "test_plugin_delete"
""",
        is_active=True,
    )

    # Manually trigger reload
    plugin_registry.reload_db_plugins()

    # Verify plugin is in registry
    assert plugin.name in plugin_registry.db_plugins

    # Delete the plugin
    plugin.delete()

    # Manually trigger reload
    plugin_registry.reload_db_plugins()

    # Clean up sys.modules
    if plugin.name in sys.modules:
        del sys.modules[plugin.name]

    # Verify plugin is removed from registry
    assert plugin.name not in plugin_registry.db_plugins


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=False)
def test_plugin_registry_no_reload_when_db_plugins_disabled():
    """Test that signals don't reload when DJANGO_RESUME_DB_PLUGINS is False."""

    # Clear registry first
    plugin_registry.clear_db_plugins()

    # Create an active plugin
    plugin = Plugin.objects.create(
        name="test_plugin_disabled",
        module="""
from django_resume.plugins import SimplePlugin

class TestPluginDisabled(SimplePlugin):
    name = "test_plugin_disabled"
""",
        is_active=True,
    )

    # Verify plugin is not in registry (since DB plugins are disabled)
    assert plugin.name not in plugin_registry.db_plugins


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_plugin_urls_are_registered():
    """Test that plugin URLs are properly registered after reload."""

    # Create an active plugin
    plugin = Plugin.objects.create(
        name="test_url_plugin",
        module="""
from django_resume.plugins import SimplePlugin

class TestUrlPlugin(SimplePlugin):
    name = "test_url_plugin"
""",
        is_active=True,
    )

    # Manually trigger reload (since signals are disabled in tests)
    plugin_registry.reload_db_plugins()

    # Verify plugin is in registry
    assert plugin.name in plugin_registry.db_plugins

    # Verify that the plugin has inline URLs
    plugin_instance = plugin_registry.db_plugins[plugin.name]
    inline_urls = plugin_instance.get_inline_urls()
    assert len(inline_urls) > 0  # Should have at least one URL pattern


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_url_cache_clearing_works():
    """Test that URL cache clearing is called during plugin reload."""

    from unittest.mock import patch

    # Mock clear_url_caches to verify it's called during reload
    with patch("django.urls.clear_url_caches") as mock_clear:
        plugin_registry.reload_db_plugins()

        # Should be called twice - once during clear and once after reload
        assert mock_clear.call_count == 2


@pytest.mark.django_db
@override_settings(DJANGO_RESUME_DB_PLUGINS=True)
def test_signals_are_disabled_during_tests():
    """Test that our signal handlers respect the DISABLE_AUTO_RELOAD setting."""

    from django.conf import settings

    # Should have auto-reload disabled in test settings
    assert getattr(settings, "DJANGO_RESUME_DISABLE_AUTO_RELOAD", False) is True

    # Create a plugin and verify signals don't trigger auto-reload
    plugin = Plugin.objects.create(
        name="test_signal_disabled",
        module="""
from django_resume.plugins import SimplePlugin

class TestSignalPlugin(SimplePlugin):
    name = "test_signal_disabled"
""",
        is_active=True,
    )

    # Plugin should NOT be automatically loaded (since auto-reload is disabled)
    assert plugin.name not in plugin_registry.db_plugins

    # But manual reload should work
    plugin_registry.reload_db_plugins()
    assert plugin.name in plugin_registry.db_plugins


@pytest.mark.django_db
@override_settings(
    DJANGO_RESUME_DB_PLUGINS=True, DJANGO_RESUME_DISABLE_AUTO_RELOAD=False
)
def test_auto_reload_works_when_enabled():
    """Test that auto-reload works when not disabled."""

    # Create a plugin with auto-reload enabled
    plugin = Plugin.objects.create(
        name="test_auto_reload",
        module="""
from django_resume.plugins import SimplePlugin

class TestAutoReloadPlugin(SimplePlugin):
    name = "test_auto_reload"
""",
        is_active=True,
    )

    # Plugin should be automatically loaded (since auto-reload is enabled)
    assert plugin.name in plugin_registry.db_plugins
