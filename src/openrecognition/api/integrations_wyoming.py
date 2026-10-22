"""Wyoming integration settings."""

from openrecognition.app_state import AppState
from openrecognition.integrator.discovery.runtime import network_discovery_context
from openrecognition.integrator.wyoming.discovery import wyoming_ports_conflict
from openrecognition.models.schemas import WyomingIntegrationPatch


def wyoming_settings_out(state: AppState) -> dict:
    s = state.settings
    return {
        "enabled": s.wyoming_enabled,
        "uri": s.wyoming_uri,
        "upstream_uri": s.wyoming_upstream_uri,
        "home_assistant_url": s.wyoming_home_assistant_url or None,
        "min_confidence": s.wyoming_min_confidence,
        "require_speaker_match": s.wyoming_require_speaker_match,
        "block_on_gate_reject": s.wyoming_block_on_gate_reject,
        "tag_speaker": s.wyoming_tag_speaker,
        "include_confidence": s.wyoming_include_confidence,
        "include_candidates": s.wyoming_include_candidates,
        "zeroconf_enabled": s.wyoming_zeroconf_enabled,
        "zeroconf_name": s.wyoming_zeroconf_name,
        "advertise_host": s.wyoming_advertise_host or None,
        "available": state.wyoming.available,
        "upstream_ready": state.wyoming.upstream_ready if s.wyoming_enabled else False,
        "zeroconf_registered": state.wyoming.zeroconf_registered if s.wyoming_enabled else False,
        "listen_error": state.wyoming.listen_error,
        "ports_conflict": wyoming_ports_conflict(s.wyoming_uri, s.wyoming_upstream_uri),
        "discovery": network_discovery_context(
            s.wyoming_uri,
            advertise_override=s.wyoming_advertise_host or None,
        ),
    }


def apply_wyoming_patch(state: AppState, body: WyomingIntegrationPatch) -> bool:
    """Persist Wyoming settings. Return True when the listener must restart."""
    s = state.settings
    restart = False

    if body.enabled is not None:
        restart = restart or body.enabled != s.wyoming_enabled
        s.wyoming_enabled = body.enabled
    if body.uri is not None:
        uri = body.uri.strip()
        restart = restart or uri != s.wyoming_uri
        s.wyoming_uri = uri
    if body.upstream_uri is not None:
        upstream = body.upstream_uri.strip()
        restart = restart or upstream != s.wyoming_upstream_uri
        s.wyoming_upstream_uri = upstream
    if body.home_assistant_url is not None:
        s.wyoming_home_assistant_url = body.home_assistant_url.strip()
    if body.min_confidence is not None:
        s.wyoming_min_confidence = body.min_confidence
    if body.require_speaker_match is not None:
        s.wyoming_require_speaker_match = body.require_speaker_match
    if body.block_on_gate_reject is not None:
        s.wyoming_block_on_gate_reject = body.block_on_gate_reject
    if body.tag_speaker is not None:
        s.wyoming_tag_speaker = body.tag_speaker
    if body.include_confidence is not None:
        s.wyoming_include_confidence = body.include_confidence
    if body.include_candidates is not None:
        s.wyoming_include_candidates = body.include_candidates
    if body.zeroconf_enabled is not None:
        restart = restart or body.zeroconf_enabled != s.wyoming_zeroconf_enabled
        s.wyoming_zeroconf_enabled = body.zeroconf_enabled
    if body.zeroconf_name is not None:
        name = body.zeroconf_name.strip()
        restart = restart or name != s.wyoming_zeroconf_name
        s.wyoming_zeroconf_name = name
    if body.advertise_host is not None:
        host = body.advertise_host.strip()
        restart = restart or host != s.wyoming_advertise_host
        s.wyoming_advertise_host = host

    state.wyoming.configure(
        enabled=s.wyoming_enabled,
        uri=s.wyoming_uri,
        upstream_uri=s.wyoming_upstream_uri,
        min_confidence=s.wyoming_min_confidence,
        require_speaker_match=s.wyoming_require_speaker_match,
        block_on_gate_reject=s.wyoming_block_on_gate_reject,
        tag_speaker=s.wyoming_tag_speaker,
        include_confidence=s.wyoming_include_confidence,
        include_candidates=s.wyoming_include_candidates,
        zeroconf_enabled=s.wyoming_zeroconf_enabled,
        zeroconf_name=s.wyoming_zeroconf_name,
        advertise_host=s.wyoming_advertise_host,
    )
    state.persist_runtime()
    return restart
