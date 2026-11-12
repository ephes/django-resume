"""Browser preview-before-create for JSON Resume file uploads (synthetic data)."""

import base64
import json
import time
from copy import deepcopy
from html import unescape

import pytest
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from django_resume.formats.json_resume import import_preview
from django_resume.formats.json_resume.import_preview import (
    IMPORT_PREVIEW_MAX_AGE_SECONDS,
    IMPORT_PREVIEW_SALT,
    ImportPreviewClaims,
    input_digest,
    sign_import_preview,
)
from django_resume.formats.json_resume.importer import (
    prepare_resume_import,
)
from django_resume.interchange.protocols import AdapterImport
from django_resume.models import Resume

IMPORT_URL = reverse("resume:json-resume-import")

LOSSY_DOCUMENT = {
    "basics": {
        "name": "Synthetic Sam",
        "email": "sam@example.invalid",
        "summary": "Invented summary for preview tests.",
        "profiles": [{"network": "Fediverse", "url": "https://example.invalid/sam"}],
    },
    "skills": [{"name": "Testing", "level": "High", "keywords": ["pytest"]}],
    "volunteer": [{"organization": "Invented Org"}],
}

# Independent, hand-written mapping/loss oracle; never derive it from prepare().
EXPECTED_MAPPED = {
    "identity": {
        "name": "Synthetic Sam",
        "email": "sam@example.invalid",
        "tagline": "",
        "phone": "",
        "github": "",
        "linkedin": "",
        "mastodon": "",
        "website": "",
        "pronouns": "",
        "location_name": "",
        "location_url": "",
        "avatar_img": "",
        "avatar_alt": "",
    },
    "about": {"title": "About", "text": "Invented summary for preview tests."},
    "skills": {"badges": ["pytest"]},
}
EXPECTED_OMITTED = {
    "awards": "source paths absent",
    "cover": "no json_resume import adapter",
    "education": "source paths absent",
    "employed_timeline": "source paths absent",
    "freelance_timeline": "no json_resume import adapter",
    "languages": "source paths absent",
    "permission_denied": "no json_resume import adapter",
    "projects": "source paths absent",
    "theme": "no json_resume import adapter",
    "token": "no json_resume import adapter",
}
LOSS_NOTES = {
    "about.title defaulted to 'About'; JSON Resume basics.summary does not include a section title",
    "basics.profiles entry 'Fediverse' is not imported",
    "skills entry 'Testing' level is not imported",
    "skills entry 'Testing' category name is not imported",
}
PRESERVATION_NOTE = "stored source JSON Resume document for exact re-export while mapped projection and plugin data remain unchanged"
IGNORED_ENVELOPE_NOTE = "did not store source JSON Resume document for exact re-export because meta.django_resume.plugin_data was ignored"
RESTORED_PLUGINS = {
    "identity": {"name": "Private envelope name"},
    "token": {"flat": {"token_required": False}},
}


def encode(document):
    return json.dumps(document).encode("utf-8")


def upload(data, name="synthetic.json"):
    return SimpleUploadedFile(name, data, content_type="application/json")


def preview(client, data, **options):
    return client.post(
        IMPORT_URL, {"file": upload(data), "action": "preview", **options}
    )


def confirm(client, data, token, **options):
    return client.post(
        IMPORT_URL,
        {"file": upload(data), "action": "create", "confirmation": token, **options},
    )


def token_from(response):
    assert "import_preview" in response.context, response.context["import_form"].errors
    return response.context["import_preview"]["confirmation"]


@pytest.fixture
def owner(django_user_model, client):
    user = django_user_model.objects.create_user(username="synthetic-owner")
    client.force_login(user)
    return user


def write_queries(queries):
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
    ]


@pytest.mark.django_db
def test_preview_renders_plan_without_writing(client, owner):
    data = encode(LOSSY_DOCUMENT)

    with CaptureQueriesContext(connection) as queries:
        response = preview(client, data, slug="sam-preview")

    assert response.status_code == 200
    assert write_queries(queries.captured_queries) == []
    assert Resume.objects.count() == 0
    content = response.content.decode()
    assert "Preview of the new resume" in content
    assert "Nothing has been created yet" in content
    assert "sam-preview" in content
    assert "Create new resume" in content
    assert "skills entry &#x27;Testing&#x27; level is not imported" in content
    assert "Source sections not imported into editable plugins: volunteer." in content
    assert 'name="confirmation"' in content
    assert "select the same file again" in content


@pytest.mark.django_db
def test_preview_and_confirm_creates_exactly_one_owned_resume(client, owner):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="sam-created", name="Sam Override"))

    response = confirm(client, data, token, slug="sam-created", name="Sam Override")

    assert response.status_code == 200
    created = Resume.objects.get()
    assert created.slug == "sam-created"
    assert created.owner == owner
    assert created.name == "Sam Override"
    assert created.plugin_data == EXPECTED_MAPPED
    assert created.integration_data["json_resume"]["source_document"] == LOSSY_DOCUMENT
    assert "Imported Sam Override." in response.content.decode()

    replay = confirm(client, data, token, slug="sam-created", name="Sam Override")
    assert "already exists" in replay.content.decode()
    assert Resume.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mode", ["portable-document", "restore-envelope", "ignore-envelope"]
)
def test_preview_creation_and_export_match_independent_loss_oracle(client, owner, mode):
    document = deepcopy(LOSSY_DOCUMENT)
    if mode != "portable-document":
        document["meta"] = {
            "django_resume": {"plugin_data": deepcopy(RESTORED_PLUGINS)}
        }
    options = {"slug": "oracle"}
    if mode == "ignore-envelope":
        options["portable_only"] = "on"
    data = encode(document)
    response = preview(client, data, **options)
    shown = response.context["import_preview"]
    plan, report = shown["plan"], shown["report"]
    restoring = mode == "restore-envelope"
    keeping_source = mode != "ignore-envelope"
    expected_plugins = RESTORED_PLUGINS if restoring else EXPECTED_MAPPED
    expected_notes = (
        {
            "restored plugin data from meta.django_resume.plugin_data",
            "accepted legacy meta.django_resume envelope without version as v1",
            PRESERVATION_NOTE,
        }
        if restoring
        else LOSS_NOTES
        | {PRESERVATION_NOTE if keeping_source else IGNORED_ENVELOPE_NOTE}
    )
    assert plan.plugin_data == expected_plugins
    assert plan.unmapped_sections == (
        ["basics", "skills", "volunteer"] if restoring else ["volunteer"]
    )
    assert report.mapped_plugins == (
        [] if restoring else ["about", "identity", "skills"]
    )
    assert report.restored_plugins == (["identity", "token"] if restoring else [])
    assert report.omitted_plugins == ({} if restoring else EXPECTED_OMITTED)
    assert report.valid and report.validation_errors == []
    assert set(report.notes) == expected_notes
    assert shown["keeps_source_document"] is keeping_source
    content = unescape(response.content.decode())
    for note in expected_notes:
        assert note in content
    assert (
        "Source sections not imported into editable plugins: "
        + ("basics, skills, volunteer." if restoring else "volunteer.")
        in content
    )
    if restoring:
        assert "Restored plugins: identity, token." in content
        assert "private envelope replaces portable adapter mapping" in content
        assert "Mapped plugins:" not in content
    else:
        assert "Mapped plugins: about, identity, skills." in content
        assert "Restored plugins:" not in content
        for plugin, reason in EXPECTED_OMITTED.items():
            assert f"{plugin}: {reason}" in content
    assert (
        "The parsed source document is kept"
        if keeping_source
        else "The source document is not kept for exact re-export in this mode."
    ) in content
    assert Resume.objects.count() == 0

    response = confirm(client, data, shown["confirmation"], **options)
    assert response.status_code == 200
    created = Resume.objects.get(slug="oracle")
    assert created.owner == owner
    assert created.name == "Synthetic Sam"
    assert created.plugin_data == expected_plugins
    state = created.integration_data["json_resume"]
    assert state["source_plugin_data"] == expected_plugins
    if keeping_source:
        assert state["source_document"] == document
    else:
        assert "source_document" not in state
    exported = client.get(reverse("resume:json-resume", kwargs={"slug": created.slug}))
    assert exported.status_code == 200
    if keeping_source:
        assert exported.json() == document
    else:
        assert exported.json() == {
            "basics": {
                "name": "Synthetic Sam",
                "email": "sam@example.invalid",
                "summary": "Invented summary for preview tests.",
            },
            "skills": [{"name": "pytest"}],
            "meta": {"django_resume": {"version": 1, "plugin_data": EXPECTED_MAPPED}},
        }


@pytest.mark.django_db
def test_prepare_resume_import_does_not_query_the_database(
    owner, django_assert_num_queries
):
    with django_assert_num_queries(0):
        prepared = prepare_resume_import(LOSSY_DOCUMENT, slug="no-db", owner=owner)
    assert prepared.plan is not None
    assert prepared.report.valid


@pytest.mark.django_db
def test_preview_requires_login_and_post(client):
    data = encode(LOSSY_DOCUMENT)

    response = preview(client, data, slug="anon")
    assert response.status_code == 302
    assert "login" in response.url
    assert client.get(IMPORT_URL).status_code in {302, 405}
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_confirmation_from_another_user_is_refused(client, owner, django_user_model):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="owned-by-first"))
    other = django_user_model.objects.create_user(username="synthetic-other")
    client.force_login(other)

    response = confirm(client, data, token, slug="owned-by-first")

    assert "preview confirmation is invalid" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_upload_without_preview_is_refused(client, owner):
    response = client.post(
        IMPORT_URL, {"file": upload(encode(LOSSY_DOCUMENT)), "slug": "direct"}
    )

    assert "Preview the uploaded file before creating" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_changed_file_is_refused(client, owner):
    token = token_from(preview(client, encode(LOSSY_DOCUMENT), slug="changed-file"))
    changed = dict(LOSSY_DOCUMENT, basics={"name": "Someone Else"})

    response = confirm(client, encode(changed), token, slug="changed-file")

    form = response.context["import_form"]
    assert "does not match the previewed file" in form.errors["file"][0]
    assert "import_preview" not in response.context
    assert Resume.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changed",
    [
        {"slug": "other-slug"},
        {"name": "Other Name"},
        {"portable_only": "on"},
    ],
)
def test_changed_options_are_refused(client, owner, changed):
    data = encode(LOSSY_DOCUMENT)
    options = {"slug": "options", "name": "Original Name"}
    token = token_from(preview(client, data, **options))

    response = confirm(client, data, token, **{**options, **changed})

    assert "changed after the preview" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_expired_confirmation_is_refused(client, owner, monkeypatch):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="expired"))
    later = time.time() + IMPORT_PREVIEW_MAX_AGE_SECONDS + 5
    monkeypatch.setattr(signing.time, "time", lambda: later)

    response = confirm(client, data, token, slug="expired")

    assert "The preview has expired" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tamper",
    [
        lambda token: token[:-2] + ("aa" if not token.endswith("aa") else "bb"),
        lambda token: "",
        lambda token: signing.dumps({"v": 1}, salt=IMPORT_PREVIEW_SALT),
        lambda token: signing.dumps(
            signing.loads(token, salt=IMPORT_PREVIEW_SALT), salt="other-salt"
        ),
    ],
    ids=["altered-signature", "missing", "malformed-claims", "wrong-salt"],
)
def test_tampered_confirmation_is_refused(client, owner, tamper):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="tampered"))

    response = confirm(client, data, tamper(token), slug="tampered")

    assert "import_report" not in response.context
    assert response.context["import_form"].errors
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_changed_plan_is_refused(client, owner):
    data = encode(LOSSY_DOCUMENT)
    forged = sign_import_preview(
        ImportPreviewClaims(
            owner=str(owner.pk),
            input_digest=input_digest(data),
            slug="plan-changed",
            name="",
            mode="restore",
            plan_digest="0" * 64,
        )
    )

    response = confirm(client, data, forged, slug="plan-changed")

    assert "import result changed since the preview" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_confirmation_carries_digests_not_resume_content(client, owner):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="digest-only"))

    payload = signing.loads(token, salt=IMPORT_PREVIEW_SALT)
    assert set(payload) == {"v", "owner", "input", "slug", "name", "mode", "plan"}
    assert payload["input"] == input_digest(data)
    raw = base64.urlsafe_b64decode(token.split(":")[0] + "==")
    assert b"sam@example.invalid" not in raw
    assert b"Invented summary" not in raw


@pytest.mark.django_db
def test_preview_refuses_existing_slug_and_keeps_existing_data(
    client, owner, django_user_model
):
    other = django_user_model.objects.create_user(username="synthetic-holder")
    Resume.objects.create(
        name="Existing", slug="taken", owner=other, plugin_data={"about": {"t": 1}}
    )

    response = preview(client, encode(LOSSY_DOCUMENT), slug="taken")

    assert "import_preview" not in response.context
    assert "already exists" in response.context["import_form"].errors["slug"][0]
    existing = Resume.objects.get()
    assert (existing.owner, existing.plugin_data) == (other, {"about": {"t": 1}})


@pytest.mark.django_db
def test_slug_taken_after_preview_preserves_existing_resume(
    client, owner, django_user_model
):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="race"))
    other = django_user_model.objects.create_user(username="synthetic-racer")
    Resume.objects.create(
        name="Winner", slug="race", owner=other, plugin_data={"about": {"t": 2}}
    )

    response = confirm(client, data, token, slug="race")

    assert "already exists" in response.context["import_form"].errors["slug"][0]
    existing = Resume.objects.get()
    assert existing.name == "Winner"
    assert existing.owner == other
    assert existing.plugin_data == {"about": {"t": 2}}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, message",
    [
        (b'{"basics": ', "Invalid JSON:"),
        (encode({"work": "not an array"}), "is not of type"),
        (
            encode({"meta": {"django_resume": {"plugin_data": []}}}),
            "meta.django_resume.plugin_data must be an object",
        ),
        (encode({"meta": {"django_resume": "x"}}), "must be an object"),
        (b'{"a": 1, "a": 2}', "Duplicate JSON object key"),
    ],
    ids=["json", "schema", "envelope", "meta", "duplicate-key"],
)
def test_invalid_inputs_get_no_preview_or_confirmation(client, owner, data, message):
    with CaptureQueriesContext(connection) as queries:
        response = preview(client, data, slug="invalid")

    assert write_queries(queries.captured_queries) == []
    assert "import_preview" not in response.context
    assert message in " ".join(response.context["import_form"].errors["file"])
    assert 'name="confirmation"' not in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_adapter_conflict_gets_no_preview(client, owner, monkeypatch):
    class _Adapter:
        source_paths = ("/basics",)

        def import_data(self, document):
            return AdapterImport(plugin_data={"name": "x"})

    class _Plugin:
        def __init__(self, name):
            self.name = name

        def get_import_adapters(self):
            return {"json_resume": _Adapter()}

    class _Registry:
        @staticmethod
        def get_all_plugins():
            return [_Plugin("a"), _Plugin("b")]

    monkeypatch.setattr(
        "django_resume.formats.json_resume.importer.plugin_registry", _Registry()
    )

    response = preview(client, encode({"basics": {"name": "X"}}), slug="conflict")

    assert "import_preview" not in response.context
    assert "Multiple import adapters claim" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_url_import_is_not_previewed(client, owner, monkeypatch):
    def fail_fetch(url):
        raise AssertionError("URL must not be fetched for a preview")

    monkeypatch.setattr("django_resume.views.load_document_url", fail_fetch)

    response = client.post(
        IMPORT_URL,
        {
            "source_url": "https://example.invalid/resume.json",
            "slug": "url-preview",
            "action": "preview",
        },
    )

    errors = response.context["import_form"].errors["source_url"]
    assert "URL imports are not previewed" in errors[0]
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_url_import_still_creates_in_one_step(client, owner, monkeypatch):
    monkeypatch.setattr(
        "django_resume.views.load_document_url",
        lambda url: {"basics": {"name": "URL Una"}},
    )

    response = client.post(
        IMPORT_URL,
        {
            "source_url": "https://example.invalid/resume.json",
            "slug": "url-una",
            "action": "import-url",
        },
    )

    assert "Imported URL Una." in response.content.decode()
    assert Resume.objects.get().owner == owner


@pytest.mark.django_db
def test_resume_list_explains_preview_and_url_behavior(client, owner):
    content = client.get(reverse("resume:list")).content.decode()

    assert "Preview new resume" in content
    assert "Import from URL" in content
    assert "URL imports are not previewed" in content
    assert "Create new resume" not in content


def test_confirmation_module_rejects_wrong_owner_before_digest():
    claims = ImportPreviewClaims(
        owner="1", input_digest="a", slug="s", name="", mode="restore", plan_digest="p"
    )
    with pytest.raises(import_preview.ImportConfirmationError) as excinfo:
        import_preview.check_confirmation_inputs(
            claims, owner="2", data_digest="a", slug="s", name="", mode="restore"
        )
    assert excinfo.value.field is None


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["import-url", "", "unknown"])
def test_upload_with_confirmation_needs_explicit_create_action(client, owner, action):
    data = encode(LOSSY_DOCUMENT)
    token = token_from(preview(client, data, slug="explicit"))

    response = client.post(
        IMPORT_URL,
        {
            "file": upload(data),
            "action": action,
            "confirmation": token,
            "slug": "explicit",
        },
    )

    assert "Preview the uploaded file before creating" in response.content.decode()
    assert Resume.objects.count() == 0


@pytest.mark.django_db
def test_sections_whose_adapters_produce_no_data_are_listed_as_unmapped(client, owner):
    document = {"basics": {"name": "Una"}, "skills": [{"level": "Expert"}]}
    prepared = prepare_resume_import(
        document, slug="unmapped", owner=owner, restore_django_resume_data=False
    )
    assert prepared.plan is not None
    assert "skills" not in prepared.plan.plugin_data
    assert "skills" in prepared.plan.unmapped_sections
    assert "basics" not in prepared.plan.unmapped_sections


@pytest.mark.django_db
def test_lone_surrogate_strings_preview_and_create(client, owner):
    data = b'{"basics": {"name": "Sur"}, "meta": {"custom": "\\ud800"}}'
    token = token_from(preview(client, data, slug="surrogate"))

    confirm(client, data, token, slug="surrogate")

    assert Resume.objects.get().slug == "surrogate"
