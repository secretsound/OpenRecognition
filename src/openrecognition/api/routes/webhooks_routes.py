"""Legacy webhook routes — prefer /v1/integrations/webhooks."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.routes.integrations import (
    create_webhook,
    delete_webhook,
    list_webhooks,
)
from openrecognition.models.schemas import WebhookSubscriptionCreate, WebhookSubscriptionOut

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"], deprecated=True)


@router.post("/subscriptions", response_model=WebhookSubscriptionOut, deprecated=True)
def create_subscription(
    body: WebhookSubscriptionCreate,
    state=Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return create_webhook(body, state, _auth)


@router.get("/subscriptions", response_model=list[WebhookSubscriptionOut], deprecated=True)
def list_subscriptions(
    state=Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return list_webhooks(state, _auth)


@router.delete("/subscriptions/{subscription_id}", status_code=204, deprecated=True)
def delete_subscription(
    subscription_id: str,
    state=Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return delete_webhook(subscription_id, state, _auth)
