"""A consumer's request-aware navigation keeps a token visitor on the CV."""

from copy import deepcopy
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("grouped", [False, True])
def test_validated_cv_navigation_click(
    page, live_server, transactional_db, django_user_model, settings, grouped
):
    from django_resume.models import Resume

    token = "synthetic+&=#ä"
    owner = django_user_model.objects.create_user(username="synthetic-nav-owner")
    Resume.objects.create(
        name="Synthetic navigation",
        slug="synthetic-nav",
        owner=owner,
        plugin_data={"token": {"items": [{"token": token}]}},
    )
    # Integrations opt into request-aware tags in their own CV navigation.
    tag = (
        "{% page_nav_groups resume request=request as groups %}"
        "{% for group in groups %}{% for link in group.links %}"
        '<a href="{{ link.url }}">{{ link.title }}</a>{% endfor %}{% endfor %}'
        if grouped
        else "{% page_nav_links resume request=request as links %}"
        '{% for link in links %}<a href="{{ link.url }}">{{ link.title }}</a>{% endfor %}'
    )
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["APP_DIRS"] = False
    templates[0]["OPTIONS"]["loaders"] = [
        (
            "django.template.loaders.locmem.Loader",
            {
                "django_resume/pages/plain/resume_cv.html": "{% load page_nav %}<h1>Synthetic private CV</h1><nav>"
                + tag
                + "</nav>",
            },
        ),
        "django.template.loaders.app_directories.Loader",
    ]
    settings.TEMPLATES = templates
    url = f"{live_server.url}/resume/synthetic-nav/cv/"
    assert page.goto(url + "?" + urlencode({"token": token})).status == 200
    cv = page.get_by_role("link", name="CV", exact=True)
    assert parse_qs(urlsplit(cv.get_attribute("href")).query) == {"token": [token]}
    for link in page.locator("nav a").all():
        if link.inner_text() != "CV":
            assert "token" not in parse_qs(urlsplit(link.get_attribute("href")).query)
    with page.expect_navigation() as navigation:
        cv.click()
    assert navigation.value.status == 200
    assert navigation.value.headers["referrer-policy"] == "no-referrer"
    expect(page.get_by_role("heading", name="Synthetic private CV")).to_be_visible()
    page.get_by_role("link", name="Cover", exact=True).click()
    assert urlsplit(page.url).query == ""
    assert page.goto(url).status == 403
