"""MCP scope filtering."""

from openrecognition.integrator.mcp.scopes import (
    filter_resources,
    filter_tools,
    tool_names,
)


def test_admin_gets_all_tools():
    names = tool_names(["admin"])
    assert "get_health" in names
    assert "enroll_from_paths" in names
    assert len(names) == 9


def test_read_only_subset():
    names = tool_names(["read"])
    assert "list_enrollments" in names
    assert "audio_gate" not in names
    assert "enroll_from_paths" not in names


def test_recognize_scope():
    names = tool_names(["recognize"])
    assert "recognize_audio" in names
    assert "list_enrollments" not in names


def test_combined_scopes():
    tools = filter_tools(["read", "enroll"])
    names = {t["name"] for t in tools}
    assert "get_presence" in names
    assert "enroll_from_paths" in names
    assert "recognize_image" not in names


def test_resources_follow_scopes():
    uris = {r["uri"] for r in filter_resources(["recognize"])}
    assert uris == set()
