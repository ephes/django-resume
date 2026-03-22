import pytest
from django.test import RequestFactory

from django_resume.plugins.base import LockedResumeMutationMixin
from django_resume.models import Resume


class DummyMutationView(LockedResumeMutationMixin):
    @staticmethod
    def check_permissions(request, resume) -> bool:
        return request.user == resume.owner


@pytest.mark.django_db
def test_mutate_resume_plugin_data_locks_and_saves_only_plugin_data(mocker, resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().post("/")
    request.user = resume.owner

    atomic = mocker.patch("django_resume.plugins.base.transaction.atomic")
    atomic.return_value.__enter__.return_value = None
    atomic.return_value.__exit__.return_value = None
    select_for_update = mocker.patch(
        "django_resume.plugins.base.Resume.objects.select_for_update",
        return_value=Resume.objects.all(),
    )
    save = mocker.patch.object(Resume, "save", autospec=True)
    view = DummyMutationView()

    def mutate(locked_resume: Resume) -> None:
        locked_resume.plugin_data["simple_plugin"] = {"foo": "bar"}

    locked_resume = view.mutate_resume_plugin_data(request, resume.pk, mutate)

    atomic.assert_called_once_with()
    select_for_update.assert_called_once_with()
    save.assert_called_once_with(locked_resume, update_fields=["plugin_data"])
    assert locked_resume.plugin_data["simple_plugin"] == {"foo": "bar"}
