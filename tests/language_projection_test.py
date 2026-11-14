"""Language selection must not fetch unrelated plugin documents."""

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from django.db import connection
from django.http import HttpResponse
from django.test.utils import CaptureQueriesContext
from django.utils import translation

from django_resume.i18n import with_resume_language


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "theme,expected",
    [
        ({"language": "de"}, "de"),
        ({"language": "xx"}, "en"),
        ({"language": True}, "en"),
        ("malformed", "en"),
        (None, "en"),
        ({"language": "true"}, "en"),
    ],
)
def test_language_query_projects_only_language(
    rf, resume, theme, expected, asynchronous
):
    resume.owner.save()
    resume.plugin_data = {"theme": theme, "irrelevant": "x" * 1000000}
    resume.save()
    queries = []

    def invoke():
        def view(request, resume_id):
            return HttpResponse(translation.get_language())

        with CaptureQueriesContext(connection) as captured:
            with translation.override("en"):
                response = with_resume_language(view)(rf.get("/"), resume_id=resume.pk)
        queries.extend(captured.captured_queries)
        return response

    async def async_view(request, resume_id):
        return HttpResponse(translation.get_language())

    async def invoke_async():
        # Capture on the thread used by Django's async ORM.
        def capture(execute, sql, params, many, context):
            queries.append({"sql": sql})
            return execute(sql, params, many, context)

        def install():
            wrapper = connection.execute_wrapper(capture)
            wrapper.__enter__()
            return wrapper

        wrapper = await sync_to_async(install)()
        try:
            with translation.override("en"):
                return await with_resume_language(async_view)(
                    rf.get("/"), resume_id=resume.pk
                )
        finally:
            await sync_to_async(wrapper.__exit__)(None, None, None)

    response = async_to_sync(invoke_async)() if asynchronous else invoke()
    assert response.content.decode() == expected
    assert len(queries) == 1
    assert "theme" in queries[0]["sql"] and "language" in queries[0]["sql"]
    assert 'SELECT "django_resume_resume"."plugin_data" FROM' not in queries[0]["sql"]
