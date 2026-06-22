import json
import os
import re
import signal
import shutil
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings

from ...models import Resume
from .export import export_resume, portable_document

NPM_SEARCH_URL = "https://registry.npmjs.org/-/v1/search"
THEME_PACKAGE_RE = re.compile(
    r"^(?:jsonresume-theme-[a-z0-9][a-z0-9._-]*|"
    r"@jsonresume/jsonresume-theme-[a-z0-9][a-z0-9._-]*)$"
)


class JsonResumeThemeError(RuntimeError):
    """Raised when theme discovery, installation, or rendering fails."""


@dataclass(frozen=True)
class ThemeSearchResult:
    name: str
    version: str
    description: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class RenderedTheme:
    html: str
    theme_name: str
    notes: tuple[str, ...]


class _OutputLimitExceeded(RuntimeError):
    def __init__(self, stream_name: str):
        super().__init__(stream_name)
        self.stream_name = stream_name


class _CapturedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


_READER_JOIN_TIMEOUT = 1.0


def is_theme_package_name(value: str) -> bool:
    return bool(THEME_PACKAGE_RE.fullmatch(value))


def cache_dir() -> Path:
    configured = getattr(settings, "DJANGO_RESUME_JSON_RESUME_THEME_DIR", None)
    if configured:
        path = Path(configured)
    else:
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        path = base_dir / ".django-resume-jsonresume-themes"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _chmod_owner_only(path, directory=True)
    return path


def selected_theme_name(resume: Resume) -> str | None:
    theme_state = _theme_state(resume)
    package = theme_state.get("package")
    return (
        package if isinstance(package, str) and is_theme_package_name(package) else None
    )


def set_selected_theme(resume: Resume, package_name: str) -> None:
    _validate_theme_name(package_name)
    integration_data = resume.integration_data
    if not isinstance(integration_data, dict):
        integration_data = {}
    json_resume_state = integration_data.get("json_resume")
    if not isinstance(json_resume_state, dict):
        json_resume_state = {}
    json_resume_state["theme"] = {"package": package_name}
    integration_data["json_resume"] = json_resume_state
    resume.integration_data = integration_data
    resume.save(update_fields=["integration_data"])


def search_themes(
    query: str = "", *, size: int = 12, timeout: float = 8.0
) -> list[ThemeSearchResult]:
    query = query.strip()
    search_text = "keywords:jsonresume-theme"
    if query:
        search_text = f"{search_text} {query}"
    params = urlencode({"text": search_text, "size": min(max(size, 1), 50)})
    url = f"{NPM_SEARCH_URL}?{params}"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise JsonResumeThemeError(f"Could not search npm registry: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JsonResumeThemeError("npm registry returned invalid JSON") from exc
    return _parse_search_results(payload)


def install_theme(package_name: str, *, timeout: float = 90.0) -> None:
    _validate_theme_name(package_name)
    npm = shutil.which("npm")
    if npm is None:
        raise JsonResumeThemeError("npm is required to install JSON Resume themes")
    target = cache_dir()
    command = [
        npm,
        "install",
        "--prefix",
        str(target),
        "--no-audit",
        "--no-fund",
        "--save",
        "resumed",
        package_name,
    ]
    completed = _run_process(command, cwd=target, timeout=timeout)
    if completed.returncode != 0:
        raise JsonResumeThemeError(_bounded_error("npm install failed", completed))


def render_selected_theme(resume: Resume, *, timeout: float = 30.0) -> RenderedTheme:
    theme_name = selected_theme_name(resume)
    if theme_name is None:
        raise JsonResumeThemeError("No JSON Resume theme is selected")
    return render_theme(resume, theme_name, timeout=timeout)


def render_theme(
    resume: Resume, theme_name: str, *, timeout: float = 30.0
) -> RenderedTheme:
    _validate_theme_name(theme_name)
    exported = export_resume(resume)
    if not exported.report.valid:
        errors = "; ".join(exported.report.validation_errors)
        raise JsonResumeThemeError(f"JSON Resume export is invalid: {errors}")
    document = portable_document(exported.document)
    target = cache_dir()
    resumed = _resumed_bin(target)
    if not resumed.exists():
        raise JsonResumeThemeError(
            "The resumed renderer is not installed; install and apply a theme first"
        )

    with tempfile.TemporaryDirectory(prefix="django-resume-jsonresume-") as tmp:
        tmp_path = Path(tmp)
        _chmod_owner_only(tmp_path, directory=True)
        resume_path = tmp_path / "resume.json"
        output_path = tmp_path / "resume.html"
        resume_path.write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
        _chmod_owner_only(resume_path)
        command = [
            str(resumed),
            "render",
            str(resume_path),
            "--theme",
            theme_name,
            "--output",
            str(output_path),
        ]
        completed = _run_process(command, cwd=target, timeout=timeout)
        if completed.returncode != 0:
            raise JsonResumeThemeError(_bounded_error("Theme render failed", completed))
        if not output_path.exists():
            raise JsonResumeThemeError("Theme render did not write an HTML output file")
        max_bytes = int(
            getattr(settings, "DJANGO_RESUME_JSON_RESUME_RENDER_MAX_BYTES", 5_000_000)
        )
        if output_path.stat().st_size > max_bytes:
            raise JsonResumeThemeError(
                f"Theme render output exceeds maximum size of {max_bytes} bytes"
            )
        html = output_path.read_text(encoding="utf-8")
    return RenderedTheme(
        html=html,
        theme_name=theme_name,
        notes=tuple(exported.report.notes),
    )


def _parse_search_results(payload: dict[str, Any]) -> list[ThemeSearchResult]:
    results = []
    for item in payload.get("objects", []):
        package = item.get("package", {}) if isinstance(item, dict) else {}
        name = package.get("name")
        if not isinstance(name, str) or not is_theme_package_name(name):
            continue
        keywords = package.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        if "jsonresume-theme" not in keywords and not name.startswith(
            ("jsonresume-theme-", "@jsonresume/jsonresume-theme-")
        ):
            continue
        results.append(
            ThemeSearchResult(
                name=name,
                version=str(package.get("version", "")),
                description=str(package.get("description", "")),
                keywords=tuple(str(keyword) for keyword in keywords),
            )
        )
    return results


def _theme_state(resume: Resume) -> dict:
    integration_data = resume.integration_data
    if not isinstance(integration_data, dict):
        return {}
    json_resume_state = integration_data.get("json_resume", {})
    if not isinstance(json_resume_state, dict):
        return {}
    theme_state = json_resume_state.get("theme", {})
    return theme_state if isinstance(theme_state, dict) else {}


def _validate_theme_name(package_name: str) -> None:
    if not is_theme_package_name(package_name):
        raise JsonResumeThemeError(f"Unsupported JSON Resume theme {package_name!r}")


def _resumed_bin(target: Path) -> Path:
    suffix = ".cmd" if os.name == "nt" else ""
    return target / "node_modules" / ".bin" / f"resumed{suffix}"


def _run_process(command: list[str], *, cwd: Path, timeout: float):
    env = _minimal_env()
    max_output_bytes = int(
        getattr(settings, "DJANGO_RESUME_JSON_RESUME_PROCESS_OUTPUT_MAX_BYTES", 200_000)
    )
    if max_output_bytes < 1:
        raise JsonResumeThemeError(
            "DJANGO_RESUME_JSON_RESUME_PROCESS_OUTPUT_MAX_BYTES must be positive"
        )
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_process_group_kwargs(),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        stdout = bytearray()
        stderr = bytearray()
        output_error: list[_OutputLimitExceeded] = []

        def read_stream(stream, buffer: bytearray, stream_name: str) -> None:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                buffer.extend(chunk)
                if len(buffer) > max_output_bytes:
                    output_error.append(_OutputLimitExceeded(stream_name))
                    _terminate_process_tree(process)
                    return

        threads = [
            threading.Thread(
                target=read_stream,
                args=(process.stdout, stdout, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=read_stream,
                args=(process.stderr, stderr, "stderr"),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            _wait_after_terminate(process)
            _close_process_streams(process)
            _join_reader_threads(threads)
            raise JsonResumeThemeError(
                f"Command timed out after {timeout:g} seconds"
            ) from exc
        if not _join_reader_threads(threads):
            _terminate_process_tree(process)
            _wait_after_terminate(process)
            _close_process_streams(process)
            _join_reader_threads(threads)
            raise JsonResumeThemeError(
                "Command output streams did not close after child process exited"
            )
        if output_error:
            stream_name = output_error[0].stream_name
            _wait_after_terminate(process)
            _close_process_streams(process)
            _join_reader_threads(threads)
            raise JsonResumeThemeError(
                f"Command {stream_name} exceeded maximum size of "
                f"{max_output_bytes} bytes"
            )
        return _CapturedProcess(
            returncode=returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )
    except subprocess.TimeoutExpired as exc:
        raise JsonResumeThemeError(
            f"Command timed out after {timeout:g} seconds"
        ) from exc
    except OSError as exc:
        raise JsonResumeThemeError(f"Could not run command: {exc}") from exc


def _process_group_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _terminate_process_tree(process) -> None:
    if os.name == "nt":
        if process.poll() is None:
            process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        if process.poll() is None:
            process.kill()


def _wait_after_terminate(process) -> None:
    try:
        process.wait(timeout=_READER_JOIN_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()


def _close_process_streams(process) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def _join_reader_threads(threads: list[threading.Thread]) -> bool:
    for thread in threads:
        thread.join(timeout=_READER_JOIN_TIMEOUT)
    return not any(thread.is_alive() for thread in threads)


def _minimal_env() -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "")}
    for key in ("SYSTEMROOT", "SystemRoot", "WINDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _bounded_error(prefix: str, completed) -> str:
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    detail = stderr or stdout or f"exit status {completed.returncode}"
    if len(detail) > 2000:
        detail = f"{detail[:2000]}..."
    return f"{prefix}: {detail}"


def _chmod_owner_only(path: Path, *, directory: bool = False) -> None:
    if os.name == "nt":
        return
    mode = stat.S_IRUSR | stat.S_IWUSR
    if directory:
        mode |= stat.S_IXUSR
    path.chmod(mode)
