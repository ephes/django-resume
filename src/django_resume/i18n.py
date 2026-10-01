"""Render a resume in its own language, independent of the site language."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from functools import wraps
from typing import Any

from django.conf import settings
from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest, HttpResponse
from django.template.response import SimpleTemplateResponse
from django.utils import translation

from .models import Resume


def language_choices() -> list[tuple[str, str]]:
    """The empty choice keeps the active site language; the rest is LANGUAGES."""
    return [("", "Site default")] + [
        (code, str(name)) for code, name in settings.LANGUAGES
    ]


def normalize_language(code: object) -> str:
    """Return ``code`` if it is one of settings.LANGUAGES, otherwise ``""``."""
    if not isinstance(code, str) or not code:
        return ""
    return code if code in dict(settings.LANGUAGES) else ""


@contextmanager
def resume_language(language: str) -> Iterator[None]:
    """Activate ``language`` for the block; an empty value changes nothing."""
    language = normalize_language(language)
    with translation.override(language) if language else nullcontext():
        yield


def render_in_language(response: HttpResponse, language: str) -> HttpResponse:
    """Make a deferred (template) response render in ``language``.

    Django renders a TemplateResponse after the view returned (and after the
    process_template_response middleware), when the view's language override
    has already ended. Wrapping the response's own render() keeps Django in
    charge of when and how it renders (including sync_to_async for async views)
    while the resume language is active during rendering."""
    language = normalize_language(language)
    if (
        language
        and isinstance(response, SimpleTemplateResponse)
        and not response.is_rendered
    ):
        render = response.render

        def render_with_language() -> SimpleTemplateResponse:
            # Drop the instance attribute before rendering: post-render
            # callbacks (cache_page) pickle the response inside render(), and a
            # local function on the instance cannot be pickled.
            response.__dict__.pop("render", None)
            with resume_language(language):
                return render()

        response.render = render_with_language  # type: ignore[method-assign]
    return response


def with_resume_language(view: Callable[..., Any]) -> Callable[..., Any]:
    """Run an inline plugin view (``resume_id`` URL kwarg) in the resume's language,
    so fragments swapped into a page match the page around them. Sync and async
    views are both supported."""

    def query(resume_id: int | str):
        return Resume.objects.filter(pk=resume_id).values_list("plugin_data", flat=True)

    if iscoroutinefunction(view):

        @wraps(view)
        async def async_wrapper(
            request: HttpRequest, *args: Any, **kwargs: Any
        ) -> HttpResponse:
            language = ""
            if kwargs.get("resume_id") is not None:
                plugin_data = await query(kwargs["resume_id"]).afirst()
                language = Resume.language_from_plugin_data(plugin_data or {})
            with resume_language(language):
                response = await view(request, *args, **kwargs)
            return render_in_language(response, language)

        return async_wrapper

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        language = ""
        if kwargs.get("resume_id") is not None:
            plugin_data = query(kwargs["resume_id"]).first()
            language = Resume.language_from_plugin_data(plugin_data or {})
        with resume_language(language):
            response = view(request, *args, **kwargs)
        return render_in_language(response, language)

    return wrapper
