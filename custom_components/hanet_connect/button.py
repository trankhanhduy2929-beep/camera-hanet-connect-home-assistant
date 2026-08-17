"""Stateless commands for HANET devices."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .coordinator import HanetCoordinator
from .entity import HanetEntity, setup_dynamic_entities


@dataclass(frozen=True, kw_only=True)
class HanetButtonDescription(ButtonEntityDescription):
    """Describe an add-on endpoint or a device command."""

    endpoint: str | None = None
    command: str | None = None
    auto_stop: bool = False


BUTTONS = (
    HanetButtonDescription(
        key="reboot",
        translation_key="reboot",
        icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        endpoint="device_reboot",
    ),
    HanetButtonDescription(
        key="open_door",
        translation_key="open_door",
        icon="mdi:door-open",
        entity_registry_enabled_default=False,
        command="open_door",
    ),
    HanetButtonDescription(
        key="close_door",
        translation_key="close_door",
        icon="mdi:door-closed",
        entity_registry_enabled_default=False,
        command="close_door",
    ),
    HanetButtonDescription(
        key="alarm",
        translation_key="alarm",
        icon="mdi:alarm-light",
        entity_registry_enabled_default=False,
        command="alarm",
    ),
    HanetButtonDescription(
        key="stop_alarm",
        translation_key="stop_alarm",
        icon="mdi:alarm-light-off",
        entity_registry_enabled_default=False,
        command="stop_alarm",
    ),
    HanetButtonDescription(
        key="ptz_up",
        translation_key="ptz_up",
        icon="mdi:arrow-up-bold",
        command="up",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_down",
        translation_key="ptz_down",
        icon="mdi:arrow-down-bold",
        command="down",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_left",
        translation_key="ptz_left",
        icon="mdi:arrow-left-bold",
        command="left",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_right",
        translation_key="ptz_right",
        icon="mdi:arrow-right-bold",
        command="right",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_zoom_in",
        translation_key="ptz_zoom_in",
        icon="mdi:magnify-plus-outline",
        command="zoomIn",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_zoom_out",
        translation_key="ptz_zoom_out",
        icon="mdi:magnify-minus-outline",
        command="zoomOut",
        auto_stop=True,
    ),
    HanetButtonDescription(
        key="ptz_auto_scan",
        translation_key="ptz_auto_scan",
        icon="mdi:pan-horizontal",
        command="autoScan",
    ),
    HanetButtonDescription(
        key="ptz_stop",
        translation_key="ptz_stop",
        icon="mdi:stop",
        command="stop",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up reboot and opt-in door/alarm command buttons."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[ButtonEntity]:
        return [
            HanetCommandButton(coordinator, str(device["id"]), description)
            for description in BUTTONS
        ]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetCommandButton(HanetEntity, ButtonEntity):
    """Send one stateless command through the gateway."""

    entity_description: HanetButtonDescription

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        description: HanetButtonDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Execute the configured command."""
        description = self.entity_description
        if description.endpoint:
            await self.coordinator.client.async_call_endpoint(
                description.endpoint, {"device_id": self.device_id}
            )
        elif description.command:
            await self.coordinator.client.async_send_command(
                self.device_id, description.command
            )
            if description.auto_stop:
                await asyncio.sleep(0.35)
                await self.coordinator.client.async_send_command(
                    self.device_id, "stop"
                )
        await self.coordinator.async_request_refresh()
