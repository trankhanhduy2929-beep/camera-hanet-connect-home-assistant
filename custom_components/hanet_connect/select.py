"""Select settings for HANET devices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .const import SELECT_SETTINGS
from .coordinator import HanetCoordinator
from .entity import (
    HanetEntity,
    has_setting,
    setting_value,
    setup_dynamic_entities,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up finite-option controls discovered on each device."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[SelectEntity]:
        device_id = str(device["id"])
        return [
            HanetSettingSelect(coordinator, device_id, key, options)
            for key, options in SELECT_SETTINGS.items()
            if has_setting(device, key)
        ]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetSettingSelect(HanetEntity, SelectEntity):
    """Control one finite-option HANET setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting: str,
        options: tuple[str, ...],
    ) -> None:
        super().__init__(coordinator, device_id, setting)
        self.setting = setting
        self.known_options = options
        self._attr_translation_key = setting

    @property
    def current_option(self) -> str | None:
        """Return the current cloud value."""
        value = setting_value(self.device, self.setting)
        return str(value) if value not in (None, "") else None

    @property
    def options(self) -> list[str]:
        """Include an unknown current value without breaking the entity."""
        options = list(self.known_options)
        current = self.current_option
        if current and current not in options:
            options.append(current)
        return options

    async def async_select_option(self, option: str) -> None:
        """Select one device option."""
        await self.coordinator.client.async_set_setting(
            self.device_id, self.setting, option
        )
        await self.coordinator.async_request_refresh()
