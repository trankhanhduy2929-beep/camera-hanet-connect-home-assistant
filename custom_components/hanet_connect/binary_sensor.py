"""Connectivity entities for HANET devices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HanetConfigEntry
from .coordinator import HanetCoordinator
from .entity import (
    HanetEntity,
    as_bool,
    event_recognition,
    setup_dynamic_entities,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up connection sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([HanetMediaBridgeSensor(coordinator)])

    def build(device: Mapping[str, Any]) -> list[BinarySensorEntity]:
        device_id = str(device["id"])
        return [
            HanetOnlineSensor(coordinator, device_id),
            HanetKnownPersonSensor(coordinator, device_id),
            HanetStrangerSensor(coordinator, device_id),
        ]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetOnlineSensor(HanetEntity, BinarySensorEntity):
    """Represent HANET cloud connectivity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, coordinator: Any, device_id: str) -> None:
        super().__init__(coordinator, device_id, "online")

    @property
    def is_on(self) -> bool:
        """Return true when the camera is online."""
        return as_bool(self.device.get("online"))


class HanetRecognitionBinarySensor(HanetEntity, BinarySensorEntity):
    """Base binary sensor backed by the latest recognition event."""

    expected_result = ""

    @property
    def event(self) -> dict[str, Any]:
        """Return the latest event for this camera."""
        return self.coordinator.latest_event(self.device_id) or {}

    @property
    def is_on(self) -> bool:
        """Return whether the latest recognition matches this sensor."""
        return event_recognition(self.event) == self.expected_result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose concise recognition details."""
        event = self.event
        return {
            key: value
            for key, value in {
                **super().extra_state_attributes,
                "person_name": event.get("person_name"),
                "event_type": event.get("kind_name") or event.get("kind"),
                "occurred_at": event.get("occurred_at"),
                "image_url": event.get("image_url"),
            }.items()
            if value not in (None, "")
        }


class HanetKnownPersonSensor(HanetRecognitionBinarySensor):
    """Report a familiar FaceID match."""

    _attr_translation_key = "known_person"
    _attr_icon = "mdi:account-check"
    expected_result = "known"

    def __init__(self, coordinator: Any, device_id: str) -> None:
        super().__init__(coordinator, device_id, "known_person")


class HanetStrangerSensor(HanetRecognitionBinarySensor):
    """Report an unknown person event."""

    _attr_translation_key = "stranger"
    _attr_icon = "mdi:account-alert"
    expected_result = "stranger"

    def __init__(self, coordinator: Any, device_id: str) -> None:
        super().__init__(coordinator, device_id, "stranger")


class HanetMediaBridgeSensor(
    CoordinatorEntity[HanetCoordinator], BinarySensorEntity
):
    """Report whether the bundled direct P2P runtime is ready."""

    _attr_has_entity_name = True
    _attr_translation_key = "media_bridge"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:cctv"

    def __init__(self, coordinator: HanetCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_media_bridge"
        )

    @property
    def is_on(self) -> bool:
        """Return true when Home Assistant can run direct P2P."""
        data = self.coordinator.data or {}
        return bool(data.get("media_bridge_connected"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a useful but secret-free P2P diagnostic."""
        data = self.coordinator.data or {}
        return {
            "configured": bool(data.get("media_bridge")),
            "authenticated": bool(
                data.get("media_bridge_authenticated")
            ),
            "error": data.get("media_bridge_error"),
        }
