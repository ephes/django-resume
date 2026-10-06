"""Signed confirmation for previewed browser file-upload imports.

The confirmation binds the authenticated owner, the exact uploaded bytes (by
digest), the normalized slug/name/mode and the prepared-plan digest. It carries
no resume bytes or plugin data: on confirmation the owner uploads the same file
again, and the server re-parses and re-prepares it before comparing digests.
Signing proves that this server issued the preview for these inputs; it says
nothing about the authenticity of the document itself.
"""

import hashlib
from dataclasses import dataclass

from django.core import signing

IMPORT_PREVIEW_MAX_AGE_SECONDS = 15 * 60
IMPORT_PREVIEW_SALT = "django_resume.json_resume.import_preview.v1"
_CLAIMS_VERSION = 1


class ImportConfirmationError(ValueError):
    """Raised when a preview confirmation is missing, expired or mismatched."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class ImportPreviewClaims:
    owner: str
    input_digest: str
    slug: str
    name: str
    mode: str
    plan_digest: str


def input_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_mode(*, portable_only: bool) -> str:
    return "portable" if portable_only else "restore"


def sign_import_preview(claims: ImportPreviewClaims) -> str:
    return signing.dumps(
        {
            "v": _CLAIMS_VERSION,
            "owner": claims.owner,
            "input": claims.input_digest,
            "slug": claims.slug,
            "name": claims.name,
            "mode": claims.mode,
            "plan": claims.plan_digest,
        },
        salt=IMPORT_PREVIEW_SALT,
    )


def load_import_preview(
    token: str, *, max_age: int = IMPORT_PREVIEW_MAX_AGE_SECONDS
) -> ImportPreviewClaims:
    if not token:
        raise ImportConfirmationError(
            "Preview the uploaded file before creating the resume."
        )
    try:
        payload = signing.loads(token, salt=IMPORT_PREVIEW_SALT, max_age=max_age)
    except signing.SignatureExpired as exc:
        raise ImportConfirmationError(
            "The preview has expired. Preview the file again before creating."
        ) from exc
    except signing.BadSignature as exc:
        raise ImportConfirmationError(
            "The preview confirmation is invalid. Preview the file again."
        ) from exc
    keys = ("owner", "input", "slug", "name", "mode", "plan")
    if (
        not isinstance(payload, dict)
        or payload.get("v") != _CLAIMS_VERSION
        or not all(isinstance(payload.get(key), str) for key in keys)
    ):
        raise ImportConfirmationError(
            "The preview confirmation is invalid. Preview the file again."
        )
    return ImportPreviewClaims(
        owner=payload["owner"],
        input_digest=payload["input"],
        slug=payload["slug"],
        name=payload["name"],
        mode=payload["mode"],
        plan_digest=payload["plan"],
    )


def check_confirmation_inputs(
    claims: ImportPreviewClaims,
    *,
    owner: str,
    data_digest: str,
    slug: str,
    name: str,
    mode: str,
) -> None:
    """Refuse a confirmation whose owner, file or options differ from preview."""
    if claims.owner != owner:
        raise ImportConfirmationError(
            "The preview confirmation is invalid. Preview the file again."
        )
    if claims.input_digest != data_digest:
        raise ImportConfirmationError(
            "The selected file does not match the previewed file. Select the "
            "same file, or preview the new file first.",
            field="file",
        )
    if (claims.slug, claims.name, claims.mode) != (slug, name, mode):
        raise ImportConfirmationError(
            "The name, slug or import mode changed after the preview. Preview "
            "again before creating."
        )


def check_confirmation_plan(claims: ImportPreviewClaims, plan_digest: str) -> None:
    if claims.plan_digest != plan_digest:
        raise ImportConfirmationError(
            "The import result changed since the preview. Preview the file again."
        )
