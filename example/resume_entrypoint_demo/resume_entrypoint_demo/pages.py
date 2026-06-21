"""The entry-point-contributed page.

``ContactPage`` is loaded by ``django_resume.pages.load_entry_point_pages()``
(via the ``django_resume.pages`` entry point in ``pyproject.toml``) and
registered before ``django_resume.urls`` is built, so it gets a real route at
``<slug>/contact/`` -- without this package being an installed Django app.

Because the package is not in ``INSTALLED_APPS``, ``APP_DIRS`` template discovery
does not see its templates, so the page renders an inline template instead. That
also keeps the proof unambiguous: the page exists *only* via the entry point.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.template import Context, Template

from django_resume.pages import ResumePage

_CONTACT_TEMPLATE = Template(
    "<!doctype html>\n"
    '<html lang="en"><head><title>Contact {{ resume.name }}</title></head>\n'
    "<body>\n"
    "  <h1>Contact {{ resume.name }}</h1>\n"
    '  <p id="entrypoint-marker">Served by an entry-point page.</p>\n'
    "</body></html>\n"
)


class ContactPage(ResumePage):
    url_name = "entrypoint_contact"
    path = "contact/"
    section_names: list[str] = []
    # No nav_title: reachable by URL, not advertised in navigation.

    def serve(self, request, resume, base_context):
        # base_context already carries ``resume`` and the edit flags.
        return HttpResponse(_CONTACT_TEMPLATE.render(Context(base_context)))
