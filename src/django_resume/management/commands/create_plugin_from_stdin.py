import os
import re
import sys
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._file_rollback import backup_files, cleanup_backups
from ._path_safety import resolve_within, validate_plugin_name


class Command(BaseCommand):
    help = "Create filesystem plugin files from stdin input"

    def handle(self, *args, **kwargs):
        self.stdout.write("Waiting for input... (Ctrl+D to end)")
        sections = re.split(r"===([^=]+)===", sys.stdin.read().strip())
        if len(sections) < 3 or sections[0].strip() or sections[2].strip():
            raise CommandError("Invalid input format")

        plugin_name = validate_plugin_name(sections[1].strip())
        names = [
            f"{plugin_name}.py",
            f"django_resume/plugins/{plugin_name}/plain/content.html",
            f"django_resume/plugins/{plugin_name}/plain/form.html",
        ]
        plugin_data = {}
        for name, source in zip(sections[3::2], sections[4::2]):
            name = name.strip()
            if name not in names or name in plugin_data:
                raise CommandError(f"Unexpected or duplicate section: {name}")
            plugin_data[name] = source
        for name in names:
            if name not in plugin_data:
                raise CommandError(f"Missing required section: {name}")
        plugin_data[names[2]] = plugin_data[names[2]].split("---")[0]
        paths = [
            resolve_within(Path.cwd() / "core/plugins", names[0]),
            resolve_within(Path.cwd() / "templates", names[1]),
            resolve_within(Path.cwd() / "templates", names[2]),
        ]
        if len(set(paths)) != len(paths):
            raise CommandError("Plugin targets must resolve to distinct files")
        staged: dict[Path, Path | None] = {}
        try:
            # Match ordinary open() permissions for new files.
            previous_umask = os.umask(0)
            os.umask(previous_umask)
            new_file_mode = 0o666 & ~previous_umask
            # Write every complete output before changing any installed file.
            for path, name in zip(paths, names):
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    prefix=f".{path.name}.stage-",
                    dir=path.parent,
                    delete=False,
                ) as output:
                    staged[path] = Path(output.name)
                    output.write(plugin_data[name])
                staged_path = staged[path]
                assert staged_path is not None
                mode = path.stat().st_mode if path.is_file() else new_file_mode
                staged_path.chmod(mode)
            with backup_files(paths):
                for path, staged_path in staged.items():
                    assert staged_path is not None
                    staged_path.replace(path)
        except OSError as error:
            raise CommandError(f"Could not create plugin: {error}") from error
        finally:
            cleanup_backups(staged)
