"""mDNS discovery for integration setup."""

from openrecognition.app_state import AppState
from openrecognition.integrator.discovery.mdns import browse_mdns


async def mdns_discovery_out(
    state: AppState,
    *,
    timeout: float,
) -> dict:
    s = state.settings
    exclude_name = s.wyoming_zeroconf_name if s.wyoming_zeroconf_enabled else None
    result = await browse_mdns(timeout=timeout, exclude_wyoming_name=exclude_name)
    return {
        "available": result.available,
        "wyoming": [
            {"name": w.name, "host": w.host, "port": w.port, "uri": w.uri}
            for w in result.wyoming
        ],
        "home_assistant": [
            {"name": h.name, "host": h.host, "port": h.port, "url": h.url}
            for h in result.home_assistant
        ],
    }
