from __future__ import annotations


class ResumePage:
    """Base class for a registered resume page. Expanded in Task 2."""

    url_name: str = ""
    path: str = ""
    template_name: str = ""
    section_names: list[str] | str = []
