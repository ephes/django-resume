#!/usr/bin/env python

import argparse
import fnmatch
import os
import sys
from pathlib import Path


def get_project_root():
    # Since the script is now in src/django_resume/entrypoints/, we need to navigate up
    return Path(__file__).parent.parent.parent.parent.resolve()


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
    args = parser.parse_args()

    def echo_filename_and_content(files, paths_only=False):
        """Print the relative path and optionally the content of each file."""
        for f in files:
            relative_path = f.relative_to(project_root)
            if paths_only:
                print(relative_path)
            else:
                print(f)
                print(relative_path)
                print("---")
                print(f.read_text())
                print("---")

    project_root = Path(get_project_root())
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
    all_files = []
    for root, dirs, files in os.walk(project_root):
        root = Path(root)
        # d is the plain directory name
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for pattern in patterns:
            for filename in fnmatch.filter(files, pattern):
                if filename not in exclude_files:
                    all_files.append(root / filename)

    # Output files
    echo_filename_and_content(all_files, args.paths_only)
    return 0


if __name__ == "__main__":
    sys.exit(llm_content())
