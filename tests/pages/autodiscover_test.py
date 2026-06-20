from django_resume.pages import autodiscover_pages


def test_autodiscover_pages_loads_resume_pages_modules(mocker):
    """``autodiscover_pages`` imports every installed app's ``resume_pages``
    module so third-party apps register pages by import side-effect.

    The module name ``"resume_pages"`` is the public contract third-party apps
    rely on, so the wrapper must delegate to ``autodiscover_modules`` with
    exactly that name. End-to-end discovery of a real installed app (the example
    project's ``PortfolioPage``) is proven by the live-server e2e test.
    """
    loader = mocker.patch("django_resume.pages.autodiscover_modules")

    autodiscover_pages()

    loader.assert_called_once_with("resume_pages")
