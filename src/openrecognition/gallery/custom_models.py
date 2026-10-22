"""Compatibility wrappers. New code should use ``model_registry``."""

from openrecognition.gallery.db import Database
from openrecognition.gallery.model_registry import (
    bind_active,
    create_custom,
    delete_custom,
    list_custom_specs,
    set_active,
    update_custom,
)
from openrecognition.gallery.model_registry import active_map as registry_active_map

__all__ = [
    "active_map",
    "apply_overrides",
    "create_custom",
    "delete_custom",
    "list_custom_specs",
    "set_active",
    "update_custom",
]


def active_map(db: Database) -> dict[str, str]:
    return registry_active_map(db)


def apply_overrides(pool, db: Database) -> None:
    bind_active(pool, db)
