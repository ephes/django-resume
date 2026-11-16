#!/usr/bin/env python

import argparse
import fnmatch
import os
import sys
import stat
from contextlib import contextmanager
from pathlib import Path
from tempfile import SpooledTemporaryFile


MAX_TREE_ENTRIES = 20_000
MAX_TREE_DEPTH = 64
MAX_FILE_BYTES = 1024 * 1024
MAX_EXPORT_BYTES = 16 * 1024 * 1024


def get_project_root():
    """Automatically select only this module's recognizable source checkout."""
    module = Path(__file__).resolve()
    root = module.parents[3]
    if not (
        (root / ".git").exists()
        and (root / "pyproject.toml").is_file()
        and (root / "README.rst").is_file()
        and root / "src/django_resume/entrypoints/llm_content.py" == module
    ):
        raise ValueError("cannot identify checkout; pass --root PROJECT_DIRECTORY")
    return root


def llm_content():
    """
    Output all relevant code / documentation in the project including
    the relative path and content of each file.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Output project files for LLM processing."
    )
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="Only show file paths without their contents",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Explicit project directory (required outside a source checkout)",
    )
    args = parser.parse_args()

    try:
        project_root = (
            args.root if args.root is not None else get_project_root()
        ).resolve(strict=True)
        if not project_root.is_dir():
            raise ValueError("root must be a directory; pass --root PROJECT_DIRECTORY")
    except (OSError, ValueError):
        parser.error("cannot select project directory; pass --root PROJECT_DIRECTORY")
    # Exclude files and directories. This is tuned to make the project fit into the
    # 200k token limit of the claude 3 models.
    exclude_files = {
        "llm_content.py",
        "package-lock.json",
        "uv.lock",
    }
    exclude_dirs = {
        ".venv",
        ".cache",
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "migrations",
        "node_modules",
        "_build",
        "example",
        "vite",
        "htmlcov",
        "scripts",
        "entrypoints",
        "dist",
    }
    patterns = ["*.py", "*.rst", "*.js", "*.ts", "*.html"]
    try:
        with (
            open_directory(project_root) as root_fd,
            SpooledTemporaryFile(
                mode="w+",
                encoding="utf-8",
                newline="\n",
                max_size=1024 * 1024,
            ) as output,
        ):
            all_files = collect_sources(root_fd, exclude_dirs, exclude_files, patterns)
            total = 0
            for relative_path in sorted(all_files):
                if args.paths_only:
                    chunk = f"{relative_path}\n"
                else:
                    with open_source(root_fd, relative_path) as source:
                        raw = source.read(MAX_FILE_BYTES + 1)
                    if len(raw) > MAX_FILE_BYTES:
                        raise ValueError("per-file byte limit exceeded")
                    content = (
                        raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                    )
                    chunk = f"{project_root / relative_path}\n{relative_path}\n---\n{content}\n---\n"
                total += len(chunk.encode("utf-8"))
                if total > MAX_EXPORT_BYTES:
                    raise ValueError("total export byte limit exceeded")
                output.write(chunk)

            # Nothing reaches stdout until the entire export passes admission.
            output.seek(0)
            while chunk := output.read(64 * 1024):
                sys.stdout.write(chunk)
    except (OSError, ValueError):
        print(
            "llm-content: refused unsafe/unreadable source or export limit exceeded; "
            "no complete export produced",
            file=sys.stderr,
        )
        return 1
    return 0


def collect_sources(root_fd, exclude_dirs, exclude_files, patterns):
    """Stream directory entries; bound retained inventory before sorting it."""
    files = []
    entries = 0
    path_bytes = 0

    def visit(directory_fd, relative, depth):
        nonlocal entries, path_bytes
        if depth > MAX_TREE_DEPTH:
            raise ValueError("directory depth limit exceeded")
        with os.scandir(directory_fd) as inventory:
            for entry in inventory:
                entries += 1
                if entries > MAX_TREE_ENTRIES:
                    raise ValueError("tree entry limit exceeded")
                path = relative / entry.name
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in exclude_dirs:
                        with open_directory(
                            entry.name, dir_fd=directory_fd
                        ) as child_fd:
                            visit(child_fd, path, depth + 1)
                elif entry.name not in exclude_files and any(
                    fnmatch.fnmatch(entry.name, pattern) for pattern in patterns
                ):
                    if not stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode):
                        raise ValueError("unsafe source entry")
                    path_bytes += len(str(path).encode("utf-8"))
                    if path_bytes > MAX_EXPORT_BYTES:
                        raise ValueError("inventory path byte limit exceeded")
                    files.append(path)

    visit(root_fd, Path(), 0)
    return files


@contextmanager
def open_directory(path, *, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def open_source(root_fd, relative_path):
    # Anchor every component to the admitted root, even after directory swaps.
    directory_fd = os.dup(root_fd)
    try:
        for component in relative_path.parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(
            relative_path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("unsafe source entry")
            yield source
    finally:
        os.close(directory_fd)


if __name__ == "__main__":
    sys.exit(llm_content())
