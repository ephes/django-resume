from html.parser import HTMLParser
from pathlib import Path

import django_resume


TEMPLATES = Path(django_resume.__file__).parent / "templates"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src", "").startswith(
            ("https://", "http://", "//")
        ):
            self.external.append(attrs)


def test_external_htmx_scripts_have_integrity_and_crossorigin():
    found = set()
    for template in sorted(TEMPLATES.rglob("*.html")):
        parser = Scripts()
        parser.feed(template.read_text())
        for script in parser.external:
            if "htmx.org" not in script["src"]:
                continue
            found.add(template.relative_to(TEMPLATES).as_posix())
            assert script.get("crossorigin") == "anonymous", template
            assert script["src"] == "https://unpkg.com/htmx.org@2.0.3", template
            assert (
                script.get("integrity")
                == "sha384-0895/pl2MU10Hqc6jd4RvrthNlDiE9U1tWmX7WRESftEDRosgxNsQG/Ze9YMRzHq"
            ), template
    assert {
        "django_resume/admin/base_change_form.html",
        "django_resume/pages/plain/base.html",
        "django_resume/pages/headwind/base.html",
        "django_resume/pages/editorial/base.html",
    } <= found
