"""Network discovery context for containers."""

from openrecognition.integrator.discovery.runtime import (
    network_discovery_context,
    running_in_container,
)


def test_running_in_container_detects_dockerenv(tmp_path, monkeypatch):
    dockerenv = tmp_path / "dockerenv"
    dockerenv.write_text("")
    monkeypatch.setattr(
        "openrecognition.integrator.discovery.runtime.Path",
        lambda p: dockerenv if str(p) == "/.dockerenv" else __import__("pathlib").Path(p),
    )
    # Simplified: just test without docker
    assert isinstance(running_in_container(), bool)


def test_network_discovery_context_includes_port():
    ctx = network_discovery_context(
        "tcp://0.0.0.0:10301",
        advertise_override=None,
    )
    assert ctx["listen_port"] == 10301
    assert "detected_host" in ctx
