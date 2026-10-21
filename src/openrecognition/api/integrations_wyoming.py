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


def apply_wyoming_patch(state: AppState, body: WyomingIntegrationPatch) -> None:
    s = state.settings
    if body.enabled is not None:
        s.wyoming_enabled = body.enabled
    if body.uri is not None:
        s.wyoming_uri = body.uri.strip()
    if body.upstream_uri is not None:
        s.wyoming_upstream_uri = body.upstream_uri.strip()
    if body.home_assistant_url is not None:
        url = body.home_assistant_url.strip()
        s.wyoming_home_assistant_url = url
    if body.min_confidence is not None:
        s.wyoming_min_confidence = body.min_confidence
    if body.require_speaker_match is not None:
        s.wyoming_require_speaker_match = body.require_speaker_match
    if body.block_on_gate_reject is not None:
        s.wyoming_block_on_gate_reject = body.block_on_gate_reject
    if body.tag_speaker is not None:
        s.wyoming_tag_speaker = body.tag_speaker
    if body.zeroconf_enabled is not None:
        s.wyoming_zeroconf_enabled = body.zeroconf_enabled
    if body.zeroconf_name is not None:
        s.wyoming_zeroconf_name = body.zeroconf_name.strip()
    if body.advertise_host is not None:
        s.wyoming_advertise_host = body.advertise_host.strip()

    state.wyoming.configure(
        enabled=s.wyoming_enabled,
        uri=s.wyoming_uri,
        upstream_uri=s.wyoming_upstream_uri,
        min_confidence=s.wyoming_min_confidence,
        require_speaker_match=s.wyoming_require_speaker_match,
        block_on_gate_reject=s.wyoming_block_on_gate_reject,
        tag_speaker=s.wyoming_tag_speaker,
        zeroconf_enabled=s.wyoming_zeroconf_enabled,
        zeroconf_name=s.wyoming_zeroconf_name,
        advertise_host=s.wyoming_advertise_host,
    )
    state.persist_runtime()
