"""Diagnostic entities for HANET Connect."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import HanetConfigEntry
from .coordinator import HanetCoordinator
from .entity import (
    HanetEntity,
    event_recognition,
    setting_leaves,
    setup_dynamic_entities,
)


@dataclass(frozen=True, kw_only=True)
class HanetDataSensorDescription(SensorEntityDescription):
    """Describe one readable camera data point."""

    keys: tuple[str, ...]


DEVICE_DATA_SENSORS = (
    HanetDataSensorDescription(
        key="model",
        translation_key="model",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        keys=("model", "device_model", "device_type_name", "device_type"),
    ),
    HanetDataSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        keys=("camera_ip", "ip", "ip_address", "local_ip"),
    ),
    HanetDataSensorDescription(
        key="storage_status",
        translation_key="storage_status",
        icon="mdi:sd",
        keys=("storage_status", "sd_status", "sdcard_status", "sd_state"),
    ),
    HanetDataSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="dBm",
        keys=("wifi_signal", "rssi", "signal"),
    ),
    HanetDataSensorDescription(
        key="resolution",
        translation_key="resolution",
        icon="mdi:video-high-definition",
        keys=("resolution", "video_quality", "quality"),
    ),
    HanetDataSensorDescription(
        key="volume",
        translation_key="volume",
        icon="mdi:volume-high",
        keys=("volume",),
    ),
    HanetDataSensorDescription(
        key="sd_free_space",
        translation_key="sd_free_space",
        icon="mdi:sd",
        keys=("sd_freesize", "sd_free_space"),
    ),
    HanetDataSensorDescription(
        key="sd_total_space",
        translation_key="sd_total_space",
        icon="mdi:sd",
        keys=("sd_spacesize", "sd_total_space"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up gateway, device and event sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([HanetGatewaySummarySensor(coordinator)])

    def build(device: Mapping[str, Any]) -> list[SensorEntity]:
        device_id = str(device["id"])
        return [
            HanetFirmwareSensor(coordinator, device_id),
            *(
                HanetDeviceDataSensor(coordinator, device_id, description)
                for description in DEVICE_DATA_SENSORS
            ),
            HanetLastEventSensor(coordinator, device_id),
            HanetLastPersonSensor(coordinator, device_id),
            HanetEventTypeSensor(coordinator, device_id),
            HanetRecognitionResultSensor(coordinator, device_id),
            HanetRecognitionTimeSensor(coordinator, device_id),
            *(
                HanetRawSettingSensor(
                    coordinator,
                    device_id,
                    setting_path,
                    label,
                )
                for setting_path, _value, label in setting_leaves(device)
            ),
        ]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )

    count_entities = [
        HanetAccountCountSensor(
            coordinator,
            "faceids",
            "faceids",
            "mdi:face-recognition",
        ),
        HanetAccountCountSensor(
            coordinator,
            "employees",
            "employees",
            "mdi:badge-account-horizontal-outline",
        ),
        HanetAccountCountSensor(
            coordinator,
            "visitors",
            "visitors",
            "mdi:account-clock-outline",
        ),
        HanetAccountCountSensor(
            coordinator,
            "departments",
            "departments",
            "mdi:office-building-outline",
        ),
    ]
    async_add_entities(count_entities)

    known_people: set[str] = set()

    @callback
    def discover_people() -> None:
        entities: list[SensorEntity] = []
        for person in coordinator.people:
            person_id = str(person.get("id") or "")
            if person_id and person_id not in known_people:
                known_people.add(person_id)
                entities.append(
                    HanetPersonLastSeenSensor(coordinator, person_id)
                )
        if entities:
            async_add_entities(entities)

    discover_people()
    entry.async_on_unload(coordinator.async_add_listener(discover_people))


class HanetGatewaySummarySensor(
    CoordinatorEntity[HanetCoordinator], SensorEntity
):
    """Summarize the account represented by this gateway."""

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_summary"
    _attr_icon = "mdi:view-dashboard-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HanetCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_gateway_summary"

    @property
    def native_value(self) -> int:
        """Return number of discovered devices."""
        return len(self.coordinator.devices)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose compact gateway counts."""
        data = self.coordinator.data or {}
        places = data.get("places")
        events = data.get("events")
        return {
            "online_devices": sum(
                bool(device.get("online")) for device in self.coordinator.devices
            ),
            "places": len(places) if isinstance(places, list) else 0,
            "recent_events": len(events) if isinstance(events, list) else 0,
            "event_connected": bool(data.get("event_connected")),
            "last_refresh": data.get("last_refresh"),
            "last_error": data.get("last_error"),
        }


class HanetFirmwareSensor(HanetEntity, SensorEntity):
    """Expose current firmware for diagnostics."""

    _attr_translation_key = "firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "firmware")

    @property
    def native_value(self) -> str | None:
        """Return the installed firmware version."""
        value = (
            self.device.get("firmware")
            or self.device.get("firmware_version")
            or self.device.get("version")
        )
        return str(value) if value not in (None, "") else None


class HanetDeviceDataSensor(HanetEntity, SensorEntity):
    """Expose one camera metadata or setting value."""

    entity_description: HanetDataSensorDescription

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        description: HanetDataSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the first available device or setting value."""
        settings = self.device.get("settings")
        sources = [self.device]
        if isinstance(settings, Mapping):
            sources.append(settings)
            sd_card = settings.get("sd_card")
            if isinstance(sd_card, Mapping):
                sources.append(sd_card)
        for source in sources:
            for key in self.entity_description.keys:
                value = source.get(key)
                if value not in (None, ""):
                    return value
        return None


class HanetRawSettingSensor(HanetEntity, SensorEntity):
    """Expose every model-specific scalar setting returned by HANET."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cog-outline"

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting_path: tuple[str, ...],
        label: str,
    ) -> None:
        digest = sha1(
            ".".join(setting_path).encode("utf-8")
        ).hexdigest()[:10]
        super().__init__(
            coordinator,
            device_id,
            f"raw_setting_{digest}",
        )
        self.setting_path = setting_path
        self._attr_name = label

    @property
    def native_value(self) -> Any:
        """Return the current scalar value at the same setting path."""
        current: Any = self.device.get("settings")
        for part in self.setting_path:
            if not isinstance(current, Mapping):
                return None
            current = current.get(part)
        if isinstance(current, bool):
            return "Bật" if current else "Tắt"
        return current if _is_sensor_value(current) else str(current)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the exact cloud key for advanced write actions."""
        return {
            **super().extra_state_attributes,
            "setting_key": ".".join(self.setting_path),
            "cloud_value_type": type(self.native_value).__name__,
        }


class HanetEventSensor(HanetEntity, SensorEntity):
    """Base sensor backed by the latest cloud event for one camera."""

    @property
    def event(self) -> dict[str, Any]:
        """Return the latest camera event."""
        return self.coordinator.latest_event(self.device_id) or {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful event details without the raw cloud payload."""
        event = self.event
        return {
            key: value
            for key, value in {
                **super().extra_state_attributes,
                "event_id": event.get("id"),
                "event_type": event.get("kind"),
                "event_type_name": event.get("kind_name"),
                "event_type_code": event.get("event_type_code"),
                "recognized": event.get("recognized"),
                "person_id": event.get("person_id"),
                "person_name": event.get("person_name"),
                "person_title": event.get("person_title"),
                "occurred_at": event.get("occurred_at"),
                "image_url": event.get("image_url"),
                "event_source": event.get("source"),
            }.items()
            if value not in (None, "")
        }


class HanetLastEventSensor(HanetEventSensor):
    """Expose the latest event title."""

    _attr_translation_key = "last_event"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_event")

    @property
    def native_value(self) -> str | None:
        """Return a concise event title."""
        value = self.event.get("title")
        return str(value)[:255] if value not in (None, "") else None


class HanetLastPersonSensor(HanetEventSensor):
    """Expose the person name attached to the latest event."""

    _attr_translation_key = "last_person"
    _attr_icon = "mdi:face-recognition"

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_person")

    @property
    def native_value(self) -> str | None:
        """Return the recognized person's name."""
        value = self.event.get("person_name")
        if value in (None, "") and event_recognition(self.event) == "stranger":
            value = "Người lạ"
        return str(value)[:255] if value not in (None, "") else None


class HanetEventTypeSensor(HanetEventSensor):
    """Expose the normalized type of the latest event."""

    _attr_translation_key = "event_type"
    _attr_icon = "mdi:shape-outline"

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "event_type")

    @property
    def native_value(self) -> str | None:
        """Return the normalized event kind."""
        value = self.event.get("kind_name") or self.event.get("kind")
        return str(value)[:255] if value not in (None, "") else None


class HanetRecognitionResultSensor(HanetEventSensor):
    """Expose a friendly known/stranger result for the latest event."""

    _attr_translation_key = "recognition_result"
    _attr_icon = "mdi:account-search"

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "recognition_result")

    @property
    def native_value(self) -> str | None:
        """Return the Vietnamese recognition result."""
        result = event_recognition(self.event)
        if result == "known":
            return "Người quen"
        if result == "stranger":
            return "Người lạ"
        return None


class HanetRecognitionTimeSensor(HanetEventSensor):
    """Expose the latest recognition as a timestamp entity."""

    _attr_translation_key = "recognition_time"
    _attr_icon = "mdi:clock-check-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "recognition_time")

    @property
    def native_value(self) -> datetime | None:
        """Return a timezone-aware event timestamp."""
        value = self.event.get("occurred_at") or self.event.get("received_at")
        if not value:
            return None
        parsed = dt_util.parse_datetime(str(value))
        if parsed is None:
            return None
        return dt_util.as_utc(parsed)


class HanetAccountCountSensor(
    CoordinatorEntity[HanetCoordinator], SensorEntity
):
    """Expose account-level FaceID and organization counts."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HanetCoordinator,
        data_key: str,
        translation_key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{data_key}_count"
        )

    @property
    def native_value(self) -> int:
        """Return the requested account count."""
        if self.data_key == "faceids":
            return len(self.coordinator.people)
        if self.data_key == "employees":
            return sum(
                str(person.get("type") or "0") != "1"
                for person in self.coordinator.people
            )
        if self.data_key == "visitors":
            return sum(
                str(person.get("type") or "") == "1"
                for person in self.coordinator.people
            )
        if self.data_key == "departments":
            return len(self.coordinator.departments)
        return 0


class HanetPersonLastSeenSensor(
    CoordinatorEntity[HanetCoordinator], SensorEntity
):
    """Expose the latest recognition timestamp for one FaceID profile."""

    _attr_icon = "mdi:account-eye"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: HanetCoordinator, person_id: str) -> None:
        super().__init__(coordinator)
        self.person_id = person_id
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_person_{person_id}_last_seen"
        )
        self._attr_has_entity_name = False

    @property
    def person(self) -> dict[str, Any]:
        """Return the current FaceID metadata."""
        return next(
            (
                person
                for person in self.coordinator.people
                if str(person.get("id") or "") == self.person_id
            ),
            {},
        )

    @property
    def name(self) -> str:
        """Return a readable Vietnamese entity name."""
        return f"Lần nhận diện {self.person.get('name') or self.person_id}"

    @property
    def native_value(self) -> datetime | None:
        """Return the most recent recognition time."""
        event = self.coordinator.latest_person_event(self.person_id) or {}
        value = event.get("occurred_at") or event.get("received_at")
        if value in (None, ""):
            return None
        parsed = dt_util.parse_datetime(str(value))
        return dt_util.as_utc(parsed) if parsed is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose profile and latest event details."""
        person = self.person
        event = self.coordinator.latest_person_event(self.person_id) or {}
        return {
            key: value
            for key, value in {
                "person_id": self.person_id,
                "person_name": person.get("name"),
                "person_type": person.get("type"),
                "person_type_name": (
                    "Khách" if str(person.get("type") or "") == "1" else "Nhân viên"
                ),
                "department": person.get("department"),
                "department_id": person.get("department_id"),
                "camera_id": event.get("device_id"),
                "camera_name": event.get("device_name"),
                "event_type": event.get("kind"),
                "image_url": event.get("image_url"),
            }.items()
            if value not in (None, "")
        }


def _is_sensor_value(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))
