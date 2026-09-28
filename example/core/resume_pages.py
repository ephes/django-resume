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

from django_resume.pages import ResumePage, by_capability, page_registry


class PortfolioPage(ResumePage):
    url_name = "portfolio"
    path = "portfolio/"
    template_name = "portfolio.html"
    # Select sections by capability instead of by name: every plugin tagged
    # "portfolio" (identity, about, skills, projects) is included, so adding a
    # new portfolio-suitable section plugin later needs no edit here.
    section_names = by_capability("portfolio")
    nav_title = "Portfolio"
    # Registered last (autodiscovered after the built-ins) yet ``nav_order``
    # places it between Cover (10) and CV (20) in the "Resume" group -- proof
    # that navigation order is explicit, not registration order.
    nav_order = 15
    nav_group = "Resume"


page_registry.register(PortfolioPage)
