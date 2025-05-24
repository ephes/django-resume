#!/usr/bin/env python

import fnmatch
import os
import sys
from pathlib import Path


def get_project_root():
    # Since the script is now in scripts/, we need to go up one level
    return Path(__file__).parent.parent.resolve()


def llm_content():
    """
    Output all relevant code / documentation in the project including
    the relative path and content of each file.
    """

    def echo_filename_and_content(files):
        """Print the relative path and content of each file."""
        for f in files:
            print(f)
            contents = f.read_text()
            relative_path = f.relative_to(project_root)
            print(relative_path)
            print("---")
            print(contents)
            print("---")

    project_root = Path(get_project_root())
    # Exclude files and directories. This is tuned to make the project fit into the
    # 200k token limit of the claude 3 models.
    exclude_files = {"llm_content.py"}
    exclude_dirs = {
        ".venv",
        "migrations",
        "node_modules",
        "_build",
        "example",
        "vite",
        "htmlcov",
        "scripts",
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
    # print("\n".join([str(f) for f in all_files]))
    echo_filename_and_content(all_files)
    return 0


if __name__ == "__main__":
    sys.exit(llm_content())
