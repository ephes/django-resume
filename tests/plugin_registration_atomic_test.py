"""Registry failures leave the exact previous plugins and routable URLs."""

from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.urls import NoReverseMatch, clear_url_caches, path, resolve, reverse

from django_resume import i18n, urls
from django_resume.plugins import SimplePlugin
from django_resume.plugins import registry as registry_module
from django_resume.plugins.registry import PluginRegistry


class FirstPlugin(SimplePlugin):
    name = "atomic_first"

    def get_inline_urls(self):
        return [path("atomic/first/", self.view, name="atomic-first")]

    def view(self, request):
        return HttpResponse("first")


class SecondPlugin(FirstPlugin):
    name = "atomic_second"

    def get_inline_urls(self):
        return [path("atomic/second/", self.view, name="atomic-second")]


class ThirdPlugin(FirstPlugin):
    name = "atomic_third"

    def get_inline_urls(self):
        return [path("atomic/third/", self.view, name="atomic-third")]


@pytest.fixture
def registry():
    original = urls.urlpatterns[:]
    registry = PluginRegistry()
    registry.register(FirstPlugin)
    yield registry
    urls.urlpatterns[:] = original
    clear_url_caches()


def snapshot(registry):
    # Warm Django's resolver before attempting replacement.
    route = reverse("django_resume:atomic-first")
    callback = resolve(route).func
    return (
        registry.plugins.copy(),
        registry.inline_urls.copy(),
        urls.urlpatterns[:],
        callback,
    )


def assert_unchanged(registry, before):
    plugins, inline_urls, patterns, callback = before
    assert registry.plugins == plugins
    assert registry.inline_urls == inline_urls
    assert urls.urlpatterns == patterns
    assert resolve(reverse("django_resume:atomic-first")).func is callback


@pytest.mark.parametrize("failure", ["constructor", "urls", "wrapper", "publication"])
def test_failed_replacement_preserves_old_routes(registry, monkeypatch, failure):
    before = snapshot(registry)

    class Replacement(FirstPlugin):
        def __init__(self):
            if failure == "constructor":
                raise RuntimeError("synthetic failure")
            super().__init__()

        def get_inline_urls(self):
            if failure == "urls":
                raise RuntimeError("synthetic failure")
            return super().get_inline_urls()

    with monkeypatch.context() as patches:
        if failure == "wrapper":

            def fail_wrapper(view):
                raise RuntimeError("synthetic failure")

            patches.setattr(i18n, "with_resume_language", fail_wrapper)
        elif failure == "publication":

            class FailOnce(dict):
                def __setitem__(self, key, value):
                    super().__setitem__(key, value)
                    raise RuntimeError("synthetic failure")

            patches.setattr(registry, "inline_urls", FailOnce(registry.inline_urls))
        with pytest.raises(RuntimeError, match="synthetic failure"):
            registry.register(Replacement)
        assert_unchanged(registry, before)

    failure = None
    registry.register(Replacement)
    assert isinstance(registry.get_plugin(FirstPlugin.name), Replacement)
    assert len(urls.urlpatterns) == len(before[2])
    assert resolve(reverse("django_resume:atomic-first")).func is not before[3]


@pytest.mark.parametrize("failure_position", [1, 2])
def test_failed_batch_is_retryable_in_input_order(registry, failure_position, mocker):
    before = snapshot(registry)
    classes = [FirstPlugin, SecondPlugin, ThirdPlugin]
    with patch.object(
        classes[failure_position],
        "get_inline_urls",
        side_effect=RuntimeError("batch failure"),
    ):
        with pytest.raises(RuntimeError, match="batch failure"):
            registry.register_plugin_list(classes)
    assert_unchanged(registry, before)
    with pytest.raises(NoReverseMatch):
        reverse("django_resume:atomic-second")

    clear = mocker.spy(registry_module, "clear_url_caches")
    registry.register_plugin_list(classes)
    clear.assert_called_once_with()
    assert [plugin.name for plugin in registry.get_all_plugins()] == [
        cls.name for cls in classes
    ]
    assert [pattern.name for pattern in urls.urlpatterns[-3:]] == [
        "atomic-first",
        "atomic-second",
        "atomic-third",
    ]
    assert len(urls.urlpatterns) == len(before[2]) + 2
    for name in ["atomic-first", "atomic-second", "atomic-third"]:
        assert resolve(reverse(f"django_resume:{name}")).url_name == name


def test_failed_wrapping_does_not_mutate_reused_patterns(registry, monkeypatch):
    before = snapshot(registry)
    reused = registry.inline_urls[FirstPlugin.name][0]
    original_callback = reused.callback

    class ReusedPlugin(FirstPlugin):
        def get_inline_urls(self):
            return [reused, path("atomic/extra/", self.view)]

    real_wrapper = i18n.with_resume_language
    wrapped = []

    def fail_second_wrapper(view):
        wrapped.append(view)
        if len(wrapped) == 2:
            raise RuntimeError("second wrapper")
        return real_wrapper(view)

    monkeypatch.setattr(i18n, "with_resume_language", fail_second_wrapper)
    with pytest.raises(RuntimeError, match="second wrapper"):
        registry.register(ReusedPlugin)
    assert len(wrapped) == 2
    assert reused.callback is original_callback
    assert_unchanged(registry, before)


def test_batch_rolls_back_publication_after_earlier_success(registry, monkeypatch):
    before = snapshot(registry)
    real_register = registry._register
    published = []

    def fail_after_publish(plugin_class):
        real_register(plugin_class)
        published.append(plugin_class)
        # Populate resolver caches from the partial batch before failing.
        clear_url_caches()
        assert reverse("django_resume:atomic-second")
        if len(published) == 2:
            raise RuntimeError("publication failure")

    monkeypatch.setattr(registry, "_register", fail_after_publish)
    with pytest.raises(RuntimeError, match="publication failure"):
        registry.register_plugin_list([SecondPlugin, ThirdPlugin])
    assert published == [SecondPlugin, ThirdPlugin]
    assert_unchanged(registry, before)
    with pytest.raises(NoReverseMatch):
        reverse("django_resume:atomic-second")
