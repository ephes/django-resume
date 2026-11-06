"""Offline failure-propagation tests for the CI audit entry point."""

from pathlib import Path
import subprocess

import pytest

from scripts import audit_python


@pytest.mark.parametrize("export_exit,audit_exit", [(0, 0), (7, 0), (0, 9)])
def test_audit_propagates_failures_and_cleans_export(
    monkeypatch, capsys, export_exit, audit_exit
):
    calls = []
    exported = []
    monkeypatch.setenv("UV_FROZEN", "1")

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True
        assert kwargs["cwd"] == audit_python.ROOT
        if command[1] == "export":
            assert "--locked" in command
            assert kwargs["env"]["UV_FROZEN"] == "false"
            assert "--all-groups" in command
            assert "--no-emit-project" in command
            assert command[command.index("--no-emit-package") + 1] == (
                "resume-entrypoint-demo"
            )
            path = Path(command[command.index("--output-file") + 1])
            exported.append(path)
            path.write_text("setuptools==84.0.0\n")
            code = export_exit
        else:
            assert "pip-audit==2.10.1" in command
            assert {"--strict", "--no-deps", "--disable-pip"} <= set(command)
            assert Path(command[-1]).read_text() == "setuptools==84.0.0\n"
            code = audit_exit
        if code:
            raise subprocess.CalledProcessError(code, command)

    monkeypatch.setattr(audit_python.subprocess, "run", run)
    assert audit_python.main() == (export_exit or audit_exit)
    assert len(calls) == (1 if export_exit else 2)
    assert not exported[0].exists()
    assert "local editable fixture, no registry version" in capsys.readouterr().out
