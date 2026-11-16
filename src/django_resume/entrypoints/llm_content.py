#!/usr/bin/env python

import argparse
import fnmatch
import os
import sys
import stat
from contextlib import contextmanager
from pathlib import Path


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
        with open_directory(project_root) as root_fd:
            all_files = []
            for directory, dirs, files, directory_fd in os.fwalk(
                ".",
                dir_fd=root_fd,
                follow_symlinks=False,
                onerror=raise_walk_error,
            ):
                dirs[:] = sorted(d for d in dirs if d not in exclude_dirs)
                for filename in sorted(files):
                    if filename in exclude_files or not any(
                        fnmatch.fnmatch(filename, pattern) for pattern in patterns
                    ):
                        continue
                    if not stat.S_ISREG(
                        os.stat(
                            filename, dir_fd=directory_fd, follow_symlinks=False
                        ).st_mode
                    ):
                        raise ValueError("unsafe source entry")
                    all_files.append(Path(directory) / filename)

            for relative_path in sorted(all_files):
                if args.paths_only:
                    print(relative_path)
                else:
                    with open_source(root_fd, relative_path) as source:
                        content = source.read().decode("utf-8")
                    print(project_root / relative_path)
                    print(relative_path)
                    print("---")
                    print(content)
                    print("---")
    except (OSError, ValueError):
        print("llm-content: refused unsafe or unreadable source entry", file=sys.stderr)
        return 1
    return 0


def raise_walk_error(error):
    raise error


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
