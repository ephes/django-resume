"""Audit the locked registry graph without installing the requirements."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print(
        "Auditing registry dependencies; excluding django-resume (this project) "
        "and resume-entrypoint-demo (local editable fixture, no registry version).",
        flush=True,
    )
    try:
        with tempfile.TemporaryDirectory() as directory:
            requirements = str(Path(directory) / "requirements.txt")
            subprocess.run(
                [
                    "uv",
                    "export",
                    "--locked",
                    "--all-groups",
                    "--no-emit-project",
                    "--no-emit-package",
                    "resume-entrypoint-demo",
                    "--no-hashes",
                    "--output-file",
                    requirements,
                ],
                cwd=ROOT,
                # CI uses UV_FROZEN for installs. Export must also reject stale locks.
                env={**os.environ, "UV_FROZEN": "false"},
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "uv",
                    "tool",
                    "run",
                    "--python",
                    sys.executable,
                    "pip-audit==2.10.1",
                    "--strict",
                    "--no-deps",
                    "--disable-pip",
                    "--cache-dir",
                    str(Path(directory) / "audit-cache"),
                    "--requirement",
                    requirements,
                ],
                cwd=ROOT,
                check=True,
            )
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
