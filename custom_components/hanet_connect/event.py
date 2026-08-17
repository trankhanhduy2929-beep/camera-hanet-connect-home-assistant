"""Recognition event entities for HANET cameras."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .const import EVENT_TYPE
from .entity import HanetEntity, setup_dynamic_entities

EVENT_TYPES = [
    "employee",
    "visitor",
    "stranger",
    "alarm",
    "human",
    "plate",
    "checkin",
    "other",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one recognition event entity for each camera."""
    coordinator = entry.runtime_data.coordinator

    def build(device: dict[str, Any]) -> list[EventEntity]:
        return [HanetRecognitionEvent(coordinator, str(device["id"]))]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetRecognitionEvent(HanetEntity, EventEntity):
    """Expose normalized employee, visitor and detection events."""

    _attr_translation_key = "recognition_event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: Any, device_id: str) -> None:
        super().__init__(coordinator, device_id, "recognition_event")

    async def async_added_to_hass(self) -> None:
        """Subscribe to integration events after the entity is registered."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_TYPE, self._handle_event)
        )

    @callback
    def _handle_event(self, event: Event) -> None:
        data = event.data
        if data.get("config_entry_id") != self.coordinator.entry.entry_id:
            return
        if str(data.get("device_id") or "") != self.device_id:
            return
        kind = str(data.get("kind") or "other")
        event_type = kind if kind in EVENT_TYPES else "other"
        attributes = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "config_entry_id",
                "raw",
                "access_token",
                "refresh_token",
            }
        }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
