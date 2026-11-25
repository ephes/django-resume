"""Render a resume in its own language, independent of the site language."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from functools import wraps
from typing import Any, TypeVar

from django.conf import settings
from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.http.response import HttpResponseBase
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


ResponseT = TypeVar("ResponseT", bound=HttpResponseBase)


def render_in_language(response: ResponseT, language: str) -> ResponseT:
    """Render deferred templates and streaming operations in ``language``.

    Django renders a TemplateResponse after the view returned (and after the
    process_template_response middleware), when the view's language override
    has already ended. Wrapping the response's own render() keeps Django in
    charge of when and how it renders (including sync_to_async for async views)
    while the resume language is active during rendering. For streams and
    unrendered templates, the latest accepted language replaces any earlier one."""
    language = normalize_language(language)
    if language and isinstance(response, StreamingHttpResponse):
        stream_language_key = "_django_resume_stream_language"
        already_wrapped = stream_language_key in response.__dict__
        response.__dict__[stream_language_key] = language
        if already_wrapped:
            return response

        content = response.streaming_content
        close = response.close

        def close_with_language() -> None:
            with resume_language(response.__dict__[stream_language_key]):
                close()

        # Use Django's public content/close interfaces: it retains ownership of
        # registered source closers, including FileResponse resources.
        response.close = close_with_language  # type: ignore[method-assign]
        # Raw file bytes do not depend on the language; leave FileResponse
        # content alone so Django keeps its wsgi.file_wrapper/sendfile path.
        if getattr(response, "file_to_stream", None) is not None:
            return response
        if response.is_async:

            async def async_content():
                iterator = aiter(content)
                while True:
                    with resume_language(response.__dict__[stream_language_key]):
                        try:
                            part = await anext(iterator)
                        except StopAsyncIteration:
                            return
                    # Never hold an override across a yield to the caller.
                    yield part

            response.streaming_content = async_content()
        else:

            def sync_content():
                iterator = iter(content)
                while True:
                    with resume_language(response.__dict__[stream_language_key]):
                        try:
                            part = next(iterator)
                        except StopIteration:
                            return
                    yield part

            response.streaming_content = sync_content()
    if (
        language
        and isinstance(response, SimpleTemplateResponse)
        and not response.is_rendered
    ):
        render_language_key = "_django_resume_render_language"
        already_wrapped = render_language_key in response.__dict__
        response.__dict__[render_language_key] = language
        if already_wrapped:
            return response

        render = response.render

        def render_with_language() -> SimpleTemplateResponse:
            # Drop the instance wrapper before rendering: post-render
            # callbacks (cache_page) pickle the response inside render(), and a
            # local function on the instance cannot be pickled.
            response.__dict__.pop("render", None)
            render_language = response.__dict__.pop(render_language_key, language)
            try:
                with resume_language(render_language):
                    return render()
            except BaseException:
                if not response.is_rendered:
                    response.__dict__[render_language_key] = render_language
                    response.render = render_with_language  # type: ignore[method-assign]
                raise

        response.render = render_with_language  # type: ignore[method-assign]
    return response


def with_resume_language(view: Callable[..., Any]) -> Callable[..., Any]:
    """Run an inline plugin view (``resume_id`` URL kwarg) in the resume's language,
    so fragments swapped into a page match the page around them. Sync and async
    views are both supported."""

    def query(resume_id: int | str):
        return Resume.objects.filter(pk=resume_id).values_list(
            "plugin_data__theme__language", flat=True
        )

    if iscoroutinefunction(view):

        @wraps(view)
        async def async_wrapper(
            request: HttpRequest, *args: Any, **kwargs: Any
        ) -> HttpResponse:
            language = ""
            if kwargs.get("resume_id") is not None:
                language = normalize_language(await query(kwargs["resume_id"]).afirst())
            with resume_language(language):
                response = await view(request, *args, **kwargs)
            return render_in_language(response, language)

        return async_wrapper

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        language = ""
        if kwargs.get("resume_id") is not None:
            language = normalize_language(query(kwargs["resume_id"]).first())
        with resume_language(language):
            response = view(request, *args, **kwargs)
        return render_in_language(response, language)

    return wrapper
