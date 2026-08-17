"""Firmware update entities for HANET devices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .coordinator import HanetCoordinator
from .entity import HanetEntity, setup_dynamic_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up firmware update entities."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[UpdateEntity]:
        return [HanetFirmwareUpdate(coordinator, str(device["id"]))]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetFirmwareUpdate(HanetEntity, UpdateEntity):
    """Request a firmware update through HANET cloud."""

    _attr_translation_key = "firmware"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: HanetCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "firmware_update")

    @property
    def installed_version(self) -> str | None:
        """Return installed firmware."""
        value = (
            self.device.get("firmware")
            or self.device.get("firmware_version")
            or self.device.get("version")
        )
        return str(value) if value not in (None, "") else None

    @property
    def latest_version(self) -> str | None:
        """Return latest firmware when reported, otherwise installed version."""
        value = (
            self.device.get("latest_firmware")
            or self.device.get("latestFirmware")
            or self.installed_version
        )
        return str(value) if value not in (None, "") else None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the cloud-selected firmware release."""
        payload: dict[str, Any] = {"device_id": self.device_id}
        if version:
            payload["version"] = version
        await self.coordinator.client.async_call_endpoint(
            "firmware_update", payload
        )
        await self.coordinator.async_request_refresh()
