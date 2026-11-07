"""A resume can render its pages in its own language."""

from tests.editor_helpers import post_current_editor


import pytest
from django.urls import reverse
from django.utils import translation

from django_resume.plugins import plugin_registry


@pytest.fixture
def german_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": "editorial", "language": "de"},
        "token": {"flat": {"token_required": False}},
        "identity": {"name": "Jane Doe", "website": "https://portfolio.example"},
        "employed_timeline": {
            "flat": {"title": "Berufserfahrung"},
            "items": [
                {
                    "id": "w1",
                    "company_name": "Beispiel GmbH",
                    "company_url": "",
                    "role": "Designerin",
                    "description": "Gestaltet.",
                    "start": "2020",
                    "end": "2024",
                    "badges": ["Kunde A"],
                    "position": 0,
                }
            ],
        },
        "permission_denied": {
            "title": "Zugang anfragen",
            "sub_title": "",
            "email": "access@example.com",
            "text": "Bitte anfragen.",
        },
    }
    resume.save()
    return resume


def test_resume_language_ignores_unknown_codes(resume):
    resume.plugin_data = {"theme": {"language": "xx"}}
    assert resume.language == ""
    resume.plugin_data = {"theme": {"language": "de"}}
    assert resume.language == "de"
    resume.plugin_data = {}
    assert resume.language == ""


@pytest.mark.django_db
def test_resume_language_overrides_site_language(client, german_resume):
    with translation.override("en"):
        cv = client.get(reverse("resume:cv", kwargs={"slug": german_resume.slug}))
        cover = client.get(
            reverse("resume:detail", kwargs={"slug": german_resume.slug})
        )

    html = cv.content.decode()
    assert '<html lang="de">' in html
    assert "<title>Lebenslauf von Jane Doe</title>" in html
    for label in ("Sprechen wir über", "Ausbildung", "Ressourcen", "Kontakt"):
        assert f'<span class="hw-text">{label}</span>' in html
    assert 'data-label="Kunden:"' in html
    assert "Drucken / als PDF speichern" in html
    assert "<title>Anschreiben — Jane Doe</title>" in cover.content.decode()
    # the site language is restored after the request
    assert translation.get_language() != "de"


@pytest.mark.django_db
def test_empty_resume_language_keeps_site_language(client, german_resume):
    german_resume.plugin_data["theme"]["language"] = ""
    german_resume.save()

    with translation.override("en"):
        html = client.get(
            reverse("resume:cv", kwargs={"slug": german_resume.slug})
        ).content.decode()

    assert '<html lang="en">' in html
    assert '<span class="hw-text">Contact</span>' in html


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_resume_language_sets_html_lang_for_other_themes(client, german_resume, theme):
    german_resume.plugin_data["theme"]["name"] = theme
    german_resume.save()

    html = client.get(
        reverse("resume:cv", kwargs={"slug": german_resume.slug})
    ).content.decode()

    assert '<html lang="de"' in html


@pytest.mark.django_db
def test_denial_page_uses_resume_language(client, german_resume):
    german_resume.plugin_data["token"]["flat"]["token_required"] = True
    german_resume.save()

    response = client.get(reverse("resume:cv", kwargs={"slug": german_resume.slug}))

    assert response.status_code == 403
    html = response.content.decode()
    assert '<html lang="de">' in html
    assert "Zugangstoken anfordern" in html


@pytest.mark.django_db
def test_inline_fragments_use_resume_language(client, german_resume):
    client.force_login(german_resume.owner)
    plugin = plugin_registry.get_plugin("employed_timeline")

    with translation.override("en"):
        response = post_current_editor(
            client,
            plugin.inline.get_post_item_url(german_resume.pk),
            {
                "id": "w1",
                "company_name": "Beispiel GmbH",
                "company_url": "",
                "role": "Designerin",
                "description": "Gestaltet.",
                "start": "2020",
                "end": "2024",
                "badges": '["Kunde A"]',
                "position": 0,
            },
        )

    assert response.status_code == 200
    assert 'data-label="Kunden:"' in response.content.decode()


@pytest.mark.django_db
def test_theme_form_saves_and_validates_language(client, german_resume):
    client.force_login(german_resume.owner)
    plugin = plugin_registry.get_plugin("theme")
    url = plugin.inline.get_post_url(german_resume.pk)

    form = client.get(plugin.inline.get_edit_url(german_resume.pk)).content.decode()
    assert '<option value="de" selected>' in form
    # the current theme is preselected, so saving the language keeps the theme
    assert '<option value="editorial" selected>' in form

    post_current_editor(client, url, {"name": "editorial", "language": "en"})
    german_resume.refresh_from_db()
    assert german_resume.plugin_data["theme"] == {"name": "editorial", "language": "en"}

    response = post_current_editor(client, url, {"name": "editorial", "language": "xx"})
    assert response.status_code == 200
    german_resume.refresh_from_db()
    assert german_resume.plugin_data["theme"]["language"] == "en"


LANGUAGE_TEMPLATE = (
    "{% load i18n %}{% get_current_language as code %}lang={{ code }}{{ extra }}"
)


def _template_response(request):
    from django.template import engines
    from django.template.response import TemplateResponse

    template = engines["django"].from_string(LANGUAGE_TEMPLATE)
    return TemplateResponse(request, template, {"extra": ""})


@pytest.mark.django_db
def test_deferred_page_response_renders_in_resume_language(rf, german_resume):
    from django.contrib.auth.models import AnonymousUser

    from django_resume.pages import ResumePage
    from django_resume.pages.base import dispatch_page

    class LanguagePage(ResumePage):
        url_name = "language-test"

        def serve(self, request, resume, base_context):
            return _template_response(request)

    request = rf.get("/")
    request.user = AnonymousUser()
    with translation.override("en"):
        response = dispatch_page(request, german_resume.slug, LanguagePage())
        # Django renders after the view and after template-response middleware
        assert not response.is_rendered
        response.context_data["extra"] = " middleware"
        response = response.render()

    assert response.content.decode() == "lang=de middleware"


@pytest.mark.django_db
def test_inline_wrapper_renders_deferred_response_in_resume_language(rf, german_resume):
    from django.http import HttpResponse

    from django_resume.i18n import with_resume_language

    def view(request, resume_id):
        response = _template_response(request)
        response.add_post_render_callback(
            lambda rendered: HttpResponse(rendered.content + b" replaced", status=201)
        )
        return response

    with translation.override("en"):
        response = with_resume_language(view)(rf.get("/"), resume_id=german_resume.pk)
        response = response.render()

    # the post-render callback's replacement response is kept
    assert response.status_code == 201
    assert response.content.decode() == "lang=de replaced"


@pytest.mark.django_db
def test_site_language_responses_are_left_alone(rf, german_resume):
    from django_resume.i18n import render_in_language

    response = _template_response(rf.get("/"))
    render = response.render

    assert render_in_language(response, "") is response
    assert response.render == render


@pytest.mark.django_db(transaction=True)
def test_inline_wrapper_supports_async_views(rf, german_resume):
    from asgiref.sync import async_to_sync, iscoroutinefunction, sync_to_async
    from django.http import HttpResponse

    from django_resume.i18n import with_resume_language

    async def async_view(request, resume_id):
        return HttpResponse(f"lang={translation.get_language()}")

    async def async_template_view(request, resume_id):
        return _template_response(request)

    view = with_resume_language(async_view)
    template_view = with_resume_language(async_template_view)
    assert iscoroutinefunction(view) and iscoroutinefunction(template_view)

    async def call_like_django():
        response = await template_view(rf.get("/"), resume_id=german_resume.pk)
        # the wrapper must not render inside the event loop; Django renders
        # deferred responses of async views through sync_to_async
        assert not response.is_rendered
        return await sync_to_async(response.render)()

    with translation.override("en"):
        response = async_to_sync(view)(rf.get("/"), resume_id=german_resume.pk)
        rendered = async_to_sync(call_like_django)()

    assert response.content.decode() == "lang=de"
    assert rendered.content.decode() == "lang=de"


@pytest.mark.django_db
def test_rendered_resume_language_response_can_be_cached(rf, german_resume):
    import pickle

    from django_resume.i18n import render_in_language

    response = render_in_language(_template_response(rf.get("/")), "de")
    response = response.render()

    assert response.content.decode() == "lang=de"
    assert pickle.loads(pickle.dumps(response)).content == response.content


@pytest.mark.django_db
def test_cache_page_view_renders_and_caches_in_resume_language(
    rf, german_resume, settings
):
    from django.core.cache import cache
    from django.views.decorators.cache import cache_page

    from django_resume.i18n import with_resume_language

    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    calls = []

    def view(request, resume_id):
        calls.append(resume_id)
        return _template_response(request)

    wrapped = with_resume_language(cache_page(60)(view))

    with translation.override("en"):
        first = wrapped(rf.get("/cached/"), resume_id=german_resume.pk).render()
        second = wrapped(rf.get("/cached/"), resume_id=german_resume.pk)

    assert first.content.decode() == "lang=de"
    assert second.content.decode() == "lang=de"
    assert len(calls) == 1  # the second request came from the cache


@pytest.mark.django_db
@pytest.mark.parametrize("replacement", [False, True])
def test_failed_deferred_render_can_retry_in_resume_language(
    rf, monkeypatch, replacement
):
    import pickle

    from django.http import HttpResponse
    from django_resume.i18n import render_in_language

    response = _template_response(rf.get("/"))
    template_render = response.template_name.render
    attempts = []

    def flaky_render(*args, **kwargs):
        attempts.append(translation.get_language())
        if len(attempts) == 1:
            raise ValueError("synthetic template failure")
        return template_render(*args, **kwargs)

    monkeypatch.setattr(response.template_name, "render", flaky_render)
    cached = []

    def cache_and_replace(rendered):
        # The wrapper must already be absent inside successful callbacks.
        cached.append(pickle.loads(pickle.dumps(rendered)).content)
        if replacement:
            return HttpResponse(rendered.content + b" replaced", status=201)

    response.add_post_render_callback(cache_and_replace)
    with translation.override("en"):
        render_in_language(response, "de")
        with pytest.raises(ValueError, match="synthetic template failure"):
            response.render()
        assert not response.is_rendered
        assert translation.get_language() == "en"
        rendered = response.render()
        assert translation.get_language() == "en"
        assert "render" not in response.__dict__
    assert attempts == ["de", "de"]
    assert cached == [b"lang=de"]
    assert rendered.content == (b"lang=de replaced" if replacement else b"lang=de")
    assert rendered.status_code == (201 if replacement else 200)
    assert pickle.loads(pickle.dumps(rendered)).content == rendered.content


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("failure", [None, "exception", "cancellation"])
def test_concurrent_async_resume_languages_are_isolated(rf, german_resume, failure):
    import asyncio

    from asgiref.sync import async_to_sync, sync_to_async
    from django_resume.i18n import with_resume_language
    from django_resume.models import Resume

    french_resume = Resume.objects.create(
        name="Synthetic French",
        slug="synthetic-french",
        owner=german_resume.owner,
        plugin_data={"theme": {"language": "fr"}},
    )
    codes = {german_resume.pk: "de", french_resume.pk: "fr"}

    async def scenario():
        arrived = {code: asyncio.Event() for code in codes.values()}
        proceed = {code: asyncio.Event() for code in codes.values()}
        observed = {code: [] for code in codes.values()}
        restored = {}

        @with_resume_language
        async def view(request, resume_id):
            code = codes[resume_id]
            observed[code].append(translation.get_language())
            arrived[code].set()
            await proceed[code].wait()
            observed[code].append(translation.get_language())
            if code == "de" and failure == "exception":
                raise ValueError("synthetic async failure")
            return _template_response(request)

        async def call(resume_id):
            assert translation.get_language() == "en"
            try:
                return await view(rf.get("/"), resume_id=resume_id)
            finally:
                restored[codes[resume_id]] = translation.get_language()

        tasks = {code: asyncio.create_task(call(pk)) for pk, code in codes.items()}
        try:
            await asyncio.wait_for(
                asyncio.gather(*(event.wait() for event in arrived.values())), 10
            )
            assert translation.get_language() == "en"
            # Finish/fail the German request while French is suspended inside
            # its override; render French later in the caller's English context.
            if failure == "cancellation":
                tasks["de"].cancel()
                with pytest.raises(asyncio.CancelledError):
                    await tasks["de"]
            else:
                proceed["de"].set()
                if failure == "exception":
                    with pytest.raises(ValueError, match="synthetic async failure"):
                        await tasks["de"]
                else:
                    german = await tasks["de"]
                    assert not german.is_rendered
                    rendered = await sync_to_async(german.render)()
                    assert rendered.content == b"lang=de"
            assert translation.get_language() == "en"
            proceed["fr"].set()
            french = await tasks["fr"]
            assert not french.is_rendered
            rendered = await sync_to_async(french.render)()
            assert rendered.content == b"lang=fr"
            assert translation.get_language() == "en"
            assert observed["fr"] == ["fr", "fr"]
            assert observed["de"] == (
                ["de"] if failure == "cancellation" else ["de", "de"]
            )
            assert restored == {"de": "en", "fr": "en"}

            # A later request in the same event loop also starts/restores cleanly.
            later = await view(rf.get("/later/"), resume_id=french_resume.pk)
            rendered = await sync_to_async(later.render)()
            assert rendered.content == b"lang=fr"
            assert translation.get_language() == "en"
        finally:
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    with translation.override("en"):
        async_to_sync(scenario)()
        assert translation.get_language() == "en"
