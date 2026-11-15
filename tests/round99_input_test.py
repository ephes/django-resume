"""Synthetic browser imports and one-shot upload inventories."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from django_resume import views
from django_resume.models import Resume
from tests.conftest import png_bytes
from tests.images_test import TwoImageForm, stored_uploads


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["preview", "create"])
@pytest.mark.parametrize("failure", ["excess", "read-error"])
def test_upload_actual_read_admission(action, failure, django_user_model, mocker):
    owner = django_user_model.objects.create_user(username="invented-import-owner")
    request = RequestFactory().post("/", {"slug": "invented", "action": action})
    request.user = owner
    reads = []

    def read(size=-1):
        reads.append(size)
        if failure == "read-error":
            raise OSError("synthetic private path")
        return b"x" * (views.MAX_INPUT_BYTES + 1)

    class SyntheticUpload(SimpleUploadedFile):
        def read(self, size=-1):
            return read(size)

    upload = SyntheticUpload("invented.json", b"{}")
    request.FILES["file"] = upload
    mocker.patch.object(views, "load_import_preview")
    prepare = mocker.spy(views, "_prepare_uploaded_import")
    sign = mocker.spy(views, "sign_import_preview")
    render = mocker.patch.object(views, "render", return_value=views.HttpResponse())
    views.import_json_resume(request)
    form = render.call_args.kwargs["context"]["import_form"]
    assert form.errors["file"]
    assert "synthetic private path" not in str(form.errors)
    assert reads == [views.MAX_INPUT_BYTES + 1]
    prepare.assert_not_called()
    sign.assert_not_called()
    assert not Resume.objects.exists()


@pytest.mark.parametrize("invalid", [False, True])
def test_one_shot_image_inventory(in_memory_storage, invalid):
    class GeneratorForm(TwoImageForm):
        def __init__(self, *args, **kwargs):
            self.image_fields = (pair for pair in TwoImageForm.image_fields)
            super().__init__(*args, **kwargs)

    form = GeneratorForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("invented.png", png_bytes(1, 1)),
            "signature_img": SimpleUploadedFile(
                "invented.png", b"invalid" if invalid else png_bytes(2, 2)
            ),
        },
    )
    assert form.is_valid() is not invalid
    if invalid:
        assert stored_uploads() == []
    else:
        assert len(stored_uploads()) == 2
        assert all(
            isinstance(form.cleaned_data[field], str)
            for field, _ in TwoImageForm.image_fields
        )
        form.cleanup_new_image_uploads()
        assert stored_uploads() == []


def test_generator_inventory_storage_failure_cleans_only_owned_files(
    in_memory_storage, monkeypatch
):
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    old = default_storage.save("uploads/preexisting.png", ContentFile(png_bytes(1, 1)))
    original_save = default_storage.save
    calls = []

    def fail_second(name, content):
        calls.append(name)
        if len(calls) == 2:
            raise OSError("synthetic storage failure")
        return original_save(name, content)

    class GeneratorForm(TwoImageForm):
        def __init__(self, *args, **kwargs):
            self.image_fields = iter(TwoImageForm.image_fields)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(default_storage, "save", fail_second)
    form = GeneratorForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("invented.png", png_bytes(1, 1)),
            "signature_img": SimpleUploadedFile("invented.png", png_bytes(2, 2)),
        },
    )
    with pytest.raises(OSError, match="synthetic storage failure"):
        form.is_valid()
    assert len(calls) == 2
    assert stored_uploads() == ["preexisting.png"]
    assert default_storage.exists(old)
