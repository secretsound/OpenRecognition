"""External integrations: webhooks, MQTT, and related connectors."""

from fastapi import APIRouter, Depends, Query

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.api.integrations_connectivity import (
    probe_home_assistant_url,
    probe_upstream_uri,
)
from openrecognition.api.integrations_discover import mdns_discovery_out
from openrecognition.api.integrations_mcp import mcp_settings_out
from openrecognition.api.integrations_mqtt import apply_mqtt_patch, mqtt_settings_out
from openrecognition.api.integrations_wyoming import apply_wyoming_patch, wyoming_settings_out
from openrecognition.app_state import AppState
from openrecognition.models.schemas import (
    IntegrationConnectivityOut,
    IntegrationsOverviewOut,
    McpIntegrationOut,
    MdnsDiscoveryOut,
    MqttIntegrationOut,
    MqttIntegrationPatch,
    WebhookSubscriptionCreate,
    WebhookSubscriptionOut,
    WyomingHomeAssistantTestIn,
    WyomingIntegrationOut,
    WyomingIntegrationPatch,
    WyomingUpstreamTestIn,
)
from openrecognition.outbound import UnsafeUrlError

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])


@router.get("", response_model=IntegrationsOverviewOut)
def get_integrations_overview(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    return IntegrationsOverviewOut(
        mqtt=MqttIntegrationOut(**mqtt_settings_out(state)),
        wyoming=WyomingIntegrationOut(**wyoming_settings_out(state)),
        mcp=McpIntegrationOut(**mcp_settings_out(state, auth)),
        webhooks=[WebhookSubscriptionOut(**s) for s in state.webhooks.list_all()],
    )


@router.get("/discover", response_model=MdnsDiscoveryOut)
async def discover_integrations(
    timeout: float = Query(3.0, ge=1.0, le=15.0, description="Seconds to listen for mDNS replies"),
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return MdnsDiscoveryOut(**await mdns_discovery_out(state, timeout=timeout))


@router.get("/mcp", response_model=McpIntegrationOut)
def get_mcp(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    return McpIntegrationOut(**mcp_settings_out(state, auth))


@router.get("/mqtt", response_model=MqttIntegrationOut)
def get_mqtt(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return MqttIntegrationOut(**mqtt_settings_out(state))


@router.patch("/mqtt", response_model=MqttIntegrationOut)
def patch_mqtt(
    body: MqttIntegrationPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    apply_mqtt_patch(state, body)
    return MqttIntegrationOut(**mqtt_settings_out(state))


@router.get("/wyoming", response_model=WyomingIntegrationOut)
def get_wyoming(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return WyomingIntegrationOut(**wyoming_settings_out(state))


@router.patch("/wyoming", response_model=WyomingIntegrationOut)
async def patch_wyoming(
    body: WyomingIntegrationPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    apply_wyoming_patch(state, body)
    await state.wyoming.restart(state)
    return WyomingIntegrationOut(**wyoming_settings_out(state))


@router.post("/wyoming/test-upstream", response_model=IntegrationConnectivityOut)
async def test_wyoming_upstream(
    body: WyomingUpstreamTestIn,
    _state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return IntegrationConnectivityOut(**await probe_upstream_uri(body.uri))


@router.post("/wyoming/test-home-assistant", response_model=IntegrationConnectivityOut)
async def test_wyoming_home_assistant(
    body: WyomingHomeAssistantTestIn,
    _state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return IntegrationConnectivityOut(**await probe_home_assistant_url(body.url))


@router.get("/webhooks", response_model=list[WebhookSubscriptionOut])
def list_webhooks(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return [WebhookSubscriptionOut(**s) for s in state.webhooks.list_all()]


@router.post("/webhooks", response_model=WebhookSubscriptionOut)
def create_webhook(
    body: WebhookSubscriptionCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        sub = state.webhooks.create(
            body.url, body.events, body.filters, body.debounce_seconds
        )
    except UnsafeUrlError as exc:
        raise bad_request("UNSAFE_URL", str(exc)) from exc
    return WebhookSubscriptionOut(**sub)


@router.delete("/webhooks/{subscription_id}", status_code=204)
def delete_webhook(
    subscription_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    if not state.webhooks.delete(subscription_id):
        raise not_found("Webhook subscription not found")
