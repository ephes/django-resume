import errno
import http.client
import json
import ipaddress
import socket
import ssl
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlparse

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import IntegrityError, transaction

from ...interchange.coordinator import (
    PathConflictError,
    build_document,
    collect_adapters,
)
from ...interchange.conflicts import detect_path_conflicts
from ...interchange.pointer import get_pointer, has_pointer
from ...interchange.report import ImportReport
from ...models import Resume
from ...plugins import plugin_registry
from .validation import validate_document

FORMAT_ID = "json_resume"
MAX_INPUT_BYTES = 2 * 1024 * 1024
URL_FETCH_TIMEOUT_SECONDS = 10
MAX_URL_REDIRECTS = 5


class JsonResumeImportError(ValueError):
    """Raised when a JSON Resume document cannot be imported."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass
class JsonResumeImport:
    resume: Resume | None
    report: ImportReport


@dataclass(frozen=True)
class _ResolvedImportURL:
    url: str
    scheme: str
    hostname: str
    port: int
    address: str
    request_target: str
    host_header: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise JsonResumeImportError(f"Duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _coerce_document(document: object) -> dict:
    if not isinstance(document, dict):
        raise JsonResumeImportError("JSON Resume document must be an object")
    return document


def _loads_document(text: str) -> dict:
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise JsonResumeImportError(f"Invalid JSON: {exc}") from exc
    return _coerce_document(document)


def load_document(path: str | Path) -> dict:
    input_path = Path(path)
    try:
        if input_path.stat().st_size > MAX_INPUT_BYTES:
            raise JsonResumeImportError(
                f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes"
            )
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise JsonResumeImportError(f"Could not read {input_path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise JsonResumeImportError(f"Invalid UTF-8 in {input_path}: {exc}") from exc
    return _loads_document(text)


def load_document_bytes(data: bytes, *, source: str = "input") -> dict:
    if len(data) > MAX_INPUT_BYTES:
        raise JsonResumeImportError(
            f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JsonResumeImportError(f"Invalid UTF-8 in {source}: {exc}") from exc
    return _loads_document(text)


def _is_public_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_global
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_private
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
    )


def _validate_import_url(url: str) -> _ResolvedImportURL:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise JsonResumeImportError(
            "JSON Resume URL must use http or https", field="source_url"
        )
    if parsed.username or parsed.password:
        raise JsonResumeImportError(
            "JSON Resume URL must not include credentials", field="source_url"
        )
    if not parsed.hostname:
        raise JsonResumeImportError(
            "JSON Resume URL must include a host", field="source_url"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise JsonResumeImportError(
            f"Invalid JSON Resume URL port: {exc}", field="source_url"
        ) from exc
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    try:
        resolved = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise JsonResumeImportError(
            f"Could not resolve JSON Resume URL: {exc}", field="source_url"
        ) from exc
    if not resolved:
        raise JsonResumeImportError(
            "Could not resolve JSON Resume URL", field="source_url"
        )
    address = str(resolved[0][4][0])
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        if not _is_public_address(str(sockaddr[0])):
            raise JsonResumeImportError(
                "JSON Resume URL host must resolve to a public address",
                field="source_url",
            )
    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"
    host_header = parsed.hostname
    if ":" in host_header and not host_header.startswith("["):
        host_header = f"[{host_header}]"
    default_port = 443 if parsed.scheme == "https" else 80
    if port != default_port:
        host_header = f"{host_header}:{port}"
    return _ResolvedImportURL(
        url=url,
        scheme=parsed.scheme,
        hostname=parsed.hostname,
        port=port,
        address=address,
        request_target=request_target,
        host_header=host_header,
    )


def _set_tcp_no_delay(sock: socket.socket) -> None:
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError as exc:
        if exc.errno != errno.ENOPROTOOPT:
            raise


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str) -> None:
        super().__init__(host, port=port, timeout=URL_FETCH_TIMEOUT_SECONDS)
        self._resolved_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._resolved_address, self.port),
            self.timeout,
        )
        _set_tcp_no_delay(self.sock)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str) -> None:
        self._ssl_context = ssl.create_default_context()
        super().__init__(
            host,
            port=port,
            timeout=URL_FETCH_TIMEOUT_SECONDS,
            context=self._ssl_context,
        )
        self._resolved_address = address

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._resolved_address, self.port),
            self.timeout,
        )
        _set_tcp_no_delay(sock)
        self.sock = self._ssl_context.wrap_socket(
            sock,
            server_hostname=self.host,
        )


def _connection_for_url(url: _ResolvedImportURL) -> http.client.HTTPConnection:
    connection_class = (
        _PinnedHTTPSConnection if url.scheme == "https" else _PinnedHTTPConnection
    )
    return connection_class(url.hostname, url.port, url.address)


def load_document_url(url: str) -> dict:
    current_url = url
    for _redirect in range(MAX_URL_REDIRECTS + 1):
        checked_url = _validate_import_url(current_url)
        connection = _connection_for_url(checked_url)
        try:
            connection.request(
                "GET",
                checked_url.request_target,
                headers={
                    "Host": checked_url.host_header,
                    "Accept": (
                        "application/json, application/schema+json;q=0.9, */*;q=0.1"
                    ),
                    "User-Agent": "django-resume-json-import",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise JsonResumeImportError(
                        "Could not read JSON Resume URL: redirect without Location",
                        field="source_url",
                    )
                current_url = urljoin(checked_url.url, location)
                continue
            if response.status >= 400:
                raise JsonResumeImportError(
                    f"Could not read JSON Resume URL: HTTP {response.status}",
                    field="source_url",
                )
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    content_length_value = int(content_length)
                except ValueError:
                    content_length_value = 0
                if content_length_value > MAX_INPUT_BYTES:
                    raise JsonResumeImportError(
                        f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes",
                        field="source_url",
                    )
            data = response.read(MAX_INPUT_BYTES + 1)
        except JsonResumeImportError:
            raise
        except (http.client.HTTPException, OSError) as exc:
            raise JsonResumeImportError(
                f"Could not read JSON Resume URL: {exc}", field="source_url"
            ) from exc
        finally:
            connection.close()
        if len(data) > MAX_INPUT_BYTES:
            raise JsonResumeImportError(
                f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes",
                field="source_url",
            )
        try:
            return load_document_bytes(data, source=checked_url.url)
        except JsonResumeImportError as exc:
            exc.field = "source_url"
            raise
    raise JsonResumeImportError(
        f"Could not read JSON Resume URL: exceeded {MAX_URL_REDIRECTS} redirects",
        field="source_url",
    )


def _validate_restored_plugin_data(plugin_data: object) -> list[str]:
    if not isinstance(plugin_data, dict):
        return ["meta.django_resume.plugin_data must be an object"]
    errors = []
    for plugin_name, payload in plugin_data.items():
        if not isinstance(plugin_name, str):
            errors.append("meta.django_resume.plugin_data keys must be strings")
        if not isinstance(payload, dict):
            errors.append(
                f"meta.django_resume.plugin_data.{plugin_name} must be an object"
            )
            continue
        if "flat" in payload and not isinstance(payload["flat"], dict):
            errors.append(
                f"meta.django_resume.plugin_data.{plugin_name}.flat must be an object"
            )
        if "items" in payload:
            if not isinstance(payload["items"], list):
                errors.append(
                    f"meta.django_resume.plugin_data.{plugin_name}.items must be a list"
                )
            elif not all(isinstance(item, dict) for item in payload["items"]):
                errors.append(
                    "meta.django_resume.plugin_data."
                    f"{plugin_name}.items must contain objects"
                )
    return errors


def _collect_adapter_plugin_data(document: dict, registry) -> tuple[dict, ImportReport]:
    plugin_data = {}
    report = ImportReport()
    adapters = []
    for plugin in registry.get_all_plugins():
        get_adapters = getattr(plugin, "get_import_adapters", None)
        adapter = get_adapters().get(FORMAT_ID) if callable(get_adapters) else None
        if adapter is None:
            report.omitted_plugins[plugin.name] = f"no {FORMAT_ID} import adapter"
            continue
        adapters.append((plugin.name, adapter))

    claims: dict[str, list[str]] = {}
    for plugin_name, adapter in adapters:
        source_paths = getattr(adapter, "source_paths", None)
        if source_paths is None:
            raise JsonResumeImportError(
                f"Import adapter for plugin {plugin_name!r} has no source_paths"
            )
        for path in source_paths:
            claims.setdefault(path, []).append(plugin_name)
    conflict = detect_path_conflicts(claims)
    if conflict is not None:
        if conflict.kind == "duplicate":
            names = ", ".join(conflict.claimers or [])
            raise JsonResumeImportError(
                f"Multiple import adapters claim source path {conflict.path!r}: {names}"
            )
        if conflict.parent is not None and conflict.child is not None:
            raise JsonResumeImportError(
                f"Overlapping import source paths {conflict.parent!r} "
                f"and {conflict.child!r}"
            )

    for plugin_name, adapter in adapters:
        if not any(has_pointer(document, path) for path in adapter.source_paths):
            report.omitted_plugins[plugin_name] = "source paths absent"
            continue
        result = adapter.import_data(document)
        report.notes.extend(result.notes)
        if result.plugin_data:
            plugin_data[plugin_name] = result.plugin_data
            report.mapped_plugins.append(plugin_name)
        else:
            report.omitted_plugins[plugin_name] = "adapter produced no plugin data"
    report.mapped_plugins.sort()
    report.omitted_plugins = dict(sorted(report.omitted_plugins.items()))
    return plugin_data, report


def _report_restored_plugin_data(plugin_data: dict) -> ImportReport:
    return ImportReport(restored_plugins=sorted(plugin_data))


def _build_source_adapter_document(
    *,
    plugin_data: dict,
    owner,
    slug: str,
    name: str,
    registry,
) -> tuple[dict | None, list[str]]:
    shadow_resume = Resume(
        name=name,
        slug=slug,
        owner=owner,
        plugin_data=deepcopy(plugin_data),
        integration_data={},
    )
    try:
        resolved, _omitted = collect_adapters(
            registry.get_all_plugins(), shadow_resume, FORMAT_ID
        )
        document, _notes = build_document(resolved)
    except PathConflictError as exc:
        return None, [
            "source JSON Resume document was not stored for exact re-export "
            f"because export adapters conflict: {exc}"
        ]
    return document, []


def _validate_resume_metadata(*, slug: str, name: str) -> None:
    slug_max_length = cast(int, Resume._meta.get_field("slug").max_length)
    if len(slug) > slug_max_length:
        raise JsonResumeImportError(
            f"Resume slug exceeds maximum length of {slug_max_length} characters",
            field="slug",
        )
    try:
        validate_slug(slug)
    except ValidationError as exc:
        raise JsonResumeImportError(
            f"Invalid resume slug {slug!r}", field="slug"
        ) from exc

    name_max_length = cast(int, Resume._meta.get_field("name").max_length)
    if len(name) > name_max_length:
        raise JsonResumeImportError(
            f"Resume name exceeds maximum length of {name_max_length} characters",
            field="name",
        )


def import_resume_document(
    document: dict,
    *,
    owner,
    slug: str,
    name: str | None = None,
    registry=None,
    restore_django_resume_data: bool = True,
) -> JsonResumeImport:
    """Create a new resume from a JSON Resume document."""
    registry = registry or plugin_registry
    errors = validate_document(document)
    if errors:
        return JsonResumeImport(
            resume=None,
            report=ImportReport(valid=False, validation_errors=errors),
        )
    if Resume.objects.filter(slug=slug).exists():
        raise JsonResumeImportError(
            f"A resume with slug {slug!r} already exists", field="slug"
        )

    django_resume_meta_value = get_pointer(document, "/meta/django_resume", None)
    if django_resume_meta_value is None:
        django_resume_meta = {}
    elif isinstance(django_resume_meta_value, dict):
        django_resume_meta = django_resume_meta_value
    else:
        return JsonResumeImport(
            resume=None,
            report=ImportReport(
                valid=False,
                validation_errors=["meta.django_resume must be an object"],
            ),
        )
    restored_plugin_data = django_resume_meta.get("plugin_data")
    if restore_django_resume_data and "plugin_data" in django_resume_meta:
        envelope_errors = _validate_restored_plugin_data(restored_plugin_data)
        if envelope_errors:
            return JsonResumeImport(
                resume=None,
                report=ImportReport(valid=False, validation_errors=envelope_errors),
            )
        restored_plugin_data = cast(dict, restored_plugin_data)
        plugin_data = deepcopy(restored_plugin_data)
        report = _report_restored_plugin_data(plugin_data)
        report.notes.append("restored plugin data from meta.django_resume.plugin_data")
    else:
        plugin_data, report = _collect_adapter_plugin_data(document, registry)

    resume_name = name or get_pointer(document, "/basics/name", "") or slug
    _validate_resume_metadata(slug=slug, name=resume_name)
    json_resume_state: dict[str, Any] = {"source_plugin_data": deepcopy(plugin_data)}
    if restore_django_resume_data or "plugin_data" not in django_resume_meta:
        json_resume_state["source_document"] = deepcopy(document)
    else:
        report.notes.append(
            "did not store source JSON Resume document for exact re-export because "
            "meta.django_resume.plugin_data was ignored"
        )
    integration_data: dict[str, Any] = {"json_resume": json_resume_state}
    source_adapter_document, source_notes = _build_source_adapter_document(
        plugin_data=plugin_data,
        owner=owner,
        slug=slug,
        name=resume_name,
        registry=registry,
    )
    report.notes.extend(source_notes)
    if source_adapter_document is not None:
        integration_data["json_resume"]["source_adapter_document"] = (
            source_adapter_document
        )
        if "source_document" in integration_data["json_resume"]:
            report.notes.append(
                "stored source JSON Resume document for exact re-export while mapped "
                "projection and plugin data remain unchanged"
            )
    preserved_extensions = django_resume_meta.get("preserved_extensions")
    if isinstance(preserved_extensions, list):
        integration_data["json_resume"]["preserved_extensions"] = deepcopy(
            preserved_extensions
        )
        report.notes.append("stored meta.django_resume.preserved_extensions")

    try:
        with transaction.atomic():
            resume = Resume.objects.create(
                name=resume_name,
                slug=slug,
                owner=owner,
                plugin_data=plugin_data,
                integration_data=integration_data,
            )
    except IntegrityError as exc:
        raise JsonResumeImportError(
            f"A resume with slug {slug!r} already exists", field="slug"
        ) from exc
    return JsonResumeImport(resume=resume, report=report)


def import_resume_file(
    path: str | Path,
    *,
    owner,
    slug: str,
    name: str | None = None,
    registry=None,
    restore_django_resume_data: bool = True,
) -> JsonResumeImport:
    document = load_document(path)
    return import_resume_document(
        document,
        owner=owner,
        slug=slug,
        name=name,
        registry=registry,
        restore_django_resume_data=restore_django_resume_data,
    )


def get_owner(username: str):
    user_model = get_user_model()
    try:
        return user_model.objects.get(**{user_model.USERNAME_FIELD: username})
    except user_model.DoesNotExist as exc:
        raise JsonResumeImportError(
            f"No user found with username {username!r}"
        ) from exc
