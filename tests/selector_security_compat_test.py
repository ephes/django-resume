"""Exercise the public selector API across the Soup Sieve security upgrade."""

import subprocess
import sys

from bs4 import BeautifulSoup


def test_deep_untrusted_document_selection_finishes():
    # CVE-2026-126190: missing ancestors used to trigger polynomial work.
    # Isolate the budget so a vulnerable lock cannot hang the test runner.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from bs4 import BeautifulSoup; "
            "soup = BeautifulSoup('<div>' * 1500 + '</div>' * 1500, 'html.parser'); "
            "assert soup.select('section div div') == []",
        ],
        check=True,
        timeout=10,
    )


def test_template_contents_are_selected_only_from_the_template():
    soup = BeautifulSoup(
        '<main><p id="visible">visible</p><template><p id="inert">inert</p></template></main>',
        "html.parser",
    )
    assert [tag["id"] for tag in soup.select("main p")] == ["visible"]
    assert [tag["id"] for tag in soup.template.select("p")] == ["inert"]
