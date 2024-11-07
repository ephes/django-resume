import pytest


def test_resume_str(resume):
    assert str(resume) == resume.name


def test_resume_repr(resume):
    assert repr(resume) == f"<{resume.name}>"


def test_token_is_required(resume):
    # Given a resume with no plugin data
    resume.plugin_data = {}

    # When we call token_is_required
    token_is_required = resume.token_is_required

    # Then it should return True
    assert token_is_required is True

    # Given a resume with plugin data
    resume.plugin_data = {"token": {"flat": {"token_required": False}}}

    # When we call token_is_required
    token_is_required = resume.token_is_required

    # Then it should return False
    assert token_is_required is False


@pytest.mark.django_db
def test_resume_plugin_data_default(resume):
    # Given a resume where plugin_data is None
    resume.plugin_data = None
    # When we save it with no plugin data
    resume.owner.save()
    resume.save()
    # Then the plugin data should be an empty dictionary
    assert resume.plugin_data == {}
