"""Capability navigation through consumer templates and the real CV route."""

from copy import deepcopy
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from django_resume.pages.base import ResumePage
from django_resume.pages.builtins import CoverLetterPage, CvPage, PermissionDeniedPage
from django_resume.pages.registry import PageRegistry
from django_resume.plugins import plugin_registry
from django_resume.templatetags import page_nav


class ExternalPage(ResumePage):
    url_name = "external"
    path = "external/"
    nav_title = "External"

    # Existing consumer overrides accept only resume, and may return any URL.
    def nav_url(self, resume):
        return "https://example.com/portfolio/?view=public"


@pytest.fixture
def navigation_resume(resume, settings, monkeypatch):
    settings.DJANGO_RESUME_TOKEN_TTL = timedelta(days=1)
    resume.owner.save()
    resume.plugin_data = {
        "token": {
            "items": [
                {"token": "cap+&=#ä", "created": timezone.now().isoformat()},
                {
                    "token": "expired",
                    "created": (timezone.now() - timedelta(days=2)).isoformat(),
                },
            ]
        },
    }
    resume.save()
    registry = PageRegistry()
    registry.register_page_list(
        [CoverLetterPage, CvPage, PermissionDeniedPage, ExternalPage]
    )
    monkeypatch.setattr(page_nav, "page_registry", registry)
    return resume


def render_links(resume, request, *, grouped=False):
    tag = (
        "{% page_nav_groups resume request=request as groups %}"
        "{% for group in groups %}{% for link in group.links %}"
        '<a href="{{ link.url }}">{{ link.title }}</a>'
        "{% endfor %}{% endfor %}"
        if grouped
        else "{% page_nav_links resume request=request as links %}"
        '{% for link in links %}<a href="{{ link.url }}">{{ link.title }}</a>{% endfor %}'
    )
    html = Template("{% load page_nav %}" + tag).render(
        Context({"resume": resume, "request": request})
    )
    return {a.text: a["href"] for a in BeautifulSoup(html, "html.parser").find_all("a")}


def token_request(token=None):
    request = RequestFactory().get("/", {"token": token} if token is not None else {})
    request.user = AnonymousUser()
    return request


@pytest.mark.django_db
@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("token_renderer", [False, True])
def test_cv_navigation_redeems_only_its_validated_capability(
    client, navigation_resume, settings, monkeypatch, grouped, token_renderer
):
    resume = navigation_resume
    if not token_renderer:
        monkeypatch.setattr(
            plugin_registry,
            "plugins",
            {
                name: plugin
                for name, plugin in plugin_registry.plugins.items()
                if name != "token"
            },
        )
    # Consumer templates opt in; no changes to the page/section extension APIs.
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["APP_DIRS"] = False
    tag = (
        "{% page_nav_groups resume request=request as groups %}"
        "{% for group in groups %}{% for link in group.links %}"
        '<a href="{{ link.url }}">{{ link.title }}</a>{% endfor %}{% endfor %}'
        if grouped
        else "{% page_nav_links resume request=request as links %}"
        '{% for link in links %}<a href="{{ link.url }}">{{ link.title }}</a>{% endfor %}'
    )
    templates[0]["OPTIONS"]["loaders"] = [
        (
            "django.template.loaders.locmem.Loader",
            {
                "django_resume/pages/plain/resume_cv.html": "{% load page_nav %}" + tag,
            },
        ),
        "django.template.loaders.app_directories.Loader",
    ]
    settings.TEMPLATES = templates
    url = reverse("resume:cv", kwargs={"slug": resume.slug})
    response = client.get(
        url, {"token": "cap+&=#ä", "edit": "true", "other": "private"}
    )
    assert response.status_code == 200
    links = {
        a.text: a["href"]
        for a in BeautifulSoup(response.content, "html.parser").find_all("a")
    }
    assert urlsplit(links["CV"]).path == url
    assert parse_qs(urlsplit(links["CV"]).query) == {"token": ["cap+&=#ä"]}
    assert all(
        "token" not in parse_qs(urlsplit(href).query)
        for title, href in links.items()
        if title != "CV"
    )
    assert client.get(links["CV"]).status_code == 200
    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "token", [None, "", "unknown", "expired", "x" * 256, "bad\x00"]
)
def test_navigation_does_not_reflect_unvalidated_tokens(navigation_resume, token):
    links = render_links(navigation_resume, token_request(token))
    assert all("token" not in parse_qs(urlsplit(url).query) for url in links.values())


@pytest.mark.django_db
@pytest.mark.parametrize("visitor", ["owner", "staff", "public"])
def test_navigation_without_token_requirement_stays_bare(
    navigation_resume, django_user_model, visitor
):
    resume = navigation_resume
    request = token_request("cap+&=#ä")
    if visitor == "owner":
        request.user = resume.owner
    elif visitor == "staff":
        request.user = django_user_model.objects.create_user(
            username="staff", is_staff=True
        )
    else:
        resume.plugin_data["token"]["flat"] = {"token_required": False}
    links = render_links(resume, request, grouped=True)
    assert links["CV"] == CvPage().nav_url(resume)


@pytest.mark.django_db
def test_token_is_not_forwarded_to_custom_cv_destination(navigation_resume):
    class CustomCv(CvPage):
        def nav_url(self, resume):
            return "https://example.com/custom-cv/"

    page_nav.page_registry.register(CustomCv)
    links = render_links(navigation_resume, token_request("cap+&=#ä"))
    assert links["CV"] == "https://example.com/custom-cv/"


@pytest.mark.django_db
def test_navigation_validates_against_the_destination_resume(navigation_resume):
    navigation_resume.plugin_data["token"] = {"items": [{"token": "different"}]}
    links = render_links(navigation_resume, token_request("cap+&=#ä"))
    assert links["CV"] == CvPage().nav_url(navigation_resume)
