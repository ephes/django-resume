"""Streaming operations and Django's close lifecycle retain resume language."""

import asyncio

import pytest
from asgiref.sync import async_to_sync
from django.http import FileResponse, StreamingHttpResponse
from django.utils import translation

from django_resume.i18n import render_in_language


@pytest.mark.django_db
@pytest.mark.parametrize("failure", [False, True])
def test_sync_streams_interleave_and_close_in_their_language(failure):
    cleanup = []

    def source():
        try:
            yield translation.get_language()
            if failure:
                raise ValueError("synthetic failure")
            yield translation.get_language()
        finally:
            cleanup.append(translation.get_language())

    with translation.override("en"):
        german = render_in_language(StreamingHttpResponse(source()), "it")
        assert render_in_language(german, "de") is german
        french = render_in_language(StreamingHttpResponse(source()), "fr")
        de, fr = iter(german), iter(french)
        assert next(de) == b"de"
        assert translation.get_language() == "en"
        assert next(fr) == b"fr"
        assert translation.get_language() == "en"
        if failure:
            with pytest.raises(ValueError, match="synthetic"):
                next(de)
        else:
            assert next(de) == b"de"
            with pytest.raises(StopIteration):
                next(de)
        assert translation.get_language() == "en"
        french.close()  # Early close before its second chunk.
        german.close()
        assert translation.get_language() == "en"
        assert cleanup == ["de", "fr"]


@pytest.mark.parametrize("ending", ["exhaust", "error", "cancel", "early-close"])
def test_async_stream_operations_and_supported_close(ending):
    cleanup = []

    class Source:
        def __init__(self):
            self.count = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            self.count += 1
            if self.count <= 2:
                await asyncio.sleep(0)
                return translation.get_language()
            if ending == "error":
                raise ValueError("synthetic failure")
            if ending == "cancel":
                try:
                    await asyncio.Future()
                finally:
                    cleanup.append(("cancel", translation.get_language()))
            raise StopAsyncIteration

        def close(self):
            # Django's public response lifecycle calls synchronous close(),
            # including for asynchronous streaming sources.
            cleanup.append(("close", translation.get_language()))

    async def scenario():
        german = render_in_language(StreamingHttpResponse(Source()), "it")
        assert render_in_language(german, "de") is german
        french = render_in_language(StreamingHttpResponse(Source()), "fr")
        de, fr = aiter(german), aiter(french)
        assert await anext(de) == b"de"
        assert translation.get_language() == "en"
        assert await anext(fr) == b"fr"
        assert translation.get_language() == "en"
        assert await anext(de) == b"de"
        assert translation.get_language() == "en"
        assert await anext(fr) == b"fr"
        assert translation.get_language() == "en"
        if ending == "cancel":
            task = asyncio.create_task(anext(de))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif ending != "early-close":
            with pytest.raises(ValueError if ending == "error" else StopAsyncIteration):
                await anext(de)
        german.close()
        french.close()
        assert translation.get_language() == "en"
        assert cleanup == (
            [("cancel", "de"), ("close", "de"), ("close", "fr")]
            if ending == "cancel"
            else [("close", "de"), ("close", "fr")]
        )

    with translation.override("en"):
        async_to_sync(scenario)()
        assert translation.get_language() == "en"


@pytest.mark.django_db
def test_page_and_inline_streams_use_selected_language(rf, resume):
    from django.contrib.auth.models import AnonymousUser
    from django_resume.i18n import with_resume_language
    from django_resume.pages import ResumePage
    from django_resume.pages.base import dispatch_page

    resume.owner.save()
    resume.plugin_data = {"theme": {"language": "de"}}
    resume.save()
    request = rf.get("/")
    request.user = AnonymousUser()

    def response():
        def chunks():
            yield translation.get_language()

        return StreamingHttpResponse(chunks())

    class Page(ResumePage):
        def serve(self, request, resume, base_context):
            return response()

    @with_resume_language
    def inline(request, resume_id):
        return response()

    with translation.override("en"):
        for streamed in (
            dispatch_page(request, resume.slug, Page()),
            inline(request, resume_id=resume.pk),
        ):
            assert b"".join(streamed) == b"de"
            streamed.close()
            assert translation.get_language() == "en"


@pytest.mark.django_db
def test_file_response_keeps_file_wrapper_and_closes_in_language(tmp_path):
    path = tmp_path / "synthetic.txt"
    path.write_bytes(b"synthetic")
    closed = []
    with translation.override("en"):
        response = FileResponse(path.open("rb"))
        response._resource_closers.append(
            lambda: closed.append(translation.get_language())
        )
        file_to_stream = response.file_to_stream
        assert file_to_stream is not None
        response = render_in_language(response, "it")
        close = response.close
        assert render_in_language(response, "de") is response
        assert response.file_to_stream is file_to_stream
        assert b"".join(response) == b"synthetic"
        response.close()
        assert file_to_stream.closed
        assert closed == ["de"]
        assert response.close is close
        assert translation.get_language() == "en"
