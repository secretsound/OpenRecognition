import sys

from openrecognition.service_restart import _restart_argv


def test_restart_argv_keeps_console_script(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/openrecognition", "serve", "--port", "9000"])
    assert _restart_argv() == ["/usr/local/bin/openrecognition", "serve", "--port", "9000"]


def test_restart_argv_rebuilds_module_invocation(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["/opt/openrecognition/cli.py", "serve"])
    assert _restart_argv() == [sys.executable, "-m", "openrecognition.cli", "serve"]
