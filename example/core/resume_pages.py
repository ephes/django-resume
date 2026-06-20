"""Example third-party page contributed by the bundled ``core`` app.

This module is the extension point in action: ``django_resume`` discovers it via
``autodiscover_pages()`` (which imports every installed app's ``resume_pages``
module on startup), so the page below is registered *before* ``django_resume.urls``
is built. No change to ``django_resume`` itself is required.

The page renders through the standard ``ResumePage`` machinery -- ``check_access``
/ ``serve`` / ``finalize_response``, themed template resolution, ``section_names``
and the existing section-plugin context -- and its content lives in the existing
section plugins' ``Resume.plugin_data``, so it needs no new model or migration.
"""

from django_resume.pages import ResumePage, page_registry


class PortfolioPage(ResumePage):
    url_name = "portfolio"
    path = "portfolio/"
    template_name = "portfolio.html"
    section_names = ["identity", "about", "skills", "projects"]


page_registry.register(PortfolioPage)
