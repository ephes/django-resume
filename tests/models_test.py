import pytest


def test_resume_str(resume):
    assert str(resume) == resume.name


def test_resume_repr(resume):
    assert repr(resume) == f"<{resume.name}>"


@pytest.mark.django_db
def test_resume_plugin_data_default(resume):
    # Given a resume where plugin_data is None
    resume.plugin_data = None
    # When we save it with no plugin data
    resume.owner.save()
    resume.save()
    # Then the plugin data should be an empty dictionary
    assert resume.plugin_data == {}
