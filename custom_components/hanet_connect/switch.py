"""Configuration switches for HANET devices."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha1
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .const import BOOL_SETTING_ALIASES, BOOL_SETTINGS
from .coordinator import HanetCoordinator
from .entity import (
    HanetEntity,
    as_bool,
    has_setting,
    setting_is_writable,
    setting_leaves,
    setting_value,
    setup_dynamic_entities,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up only the settings discovered on each device."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[SwitchEntity]:
        device_id = str(device["id"])
        entities: list[SwitchEntity] = []
        known_paths: set[str] = set()
        for translation_key, icon in BOOL_SETTINGS.items():
            aliases = BOOL_SETTING_ALIASES.get(
                translation_key, (translation_key,)
            )
            setting = next(
                (
                    alias
                    for alias in aliases
                    if has_setting(device, alias)
                ),
                None,
            )
            if setting:
                known_paths.add(_canonical_path(setting))
                entities.append(
                    HanetSettingSwitch(
                        coordinator,
                        device_id,
                        setting,
                        translation_key,
                        icon,
                    )
                )
        for path, value, label in setting_leaves(device):
            setting = ".".join(path)
            if (
                _canonical_path(setting) in known_paths
                or not setting_is_writable(path)
                or not _looks_boolean(path, value)
            ):
                continue
            entities.append(
                HanetDynamicSettingSwitch(
                    coordinator,
                    device_id,
                    setting,
                    label,
                )
            )
        return entities

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetSettingSwitch(HanetEntity, SwitchEntity):
    """Control one boolean setting from the mobile application."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting: str,
        translation_key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, device_id, translation_key)
        self.setting = setting
        self._attr_translation_key = translation_key
        self._attr_icon = f"mdi:{icon}"

    @property
    def is_on(self) -> bool:
        """Return the current setting."""
        return as_bool(setting_value(self.device, self.setting))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this device setting."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this device setting."""
        await self._set(False)

    async def _set(self, value: bool) -> None:
        await self.coordinator.client.async_set_setting(
            self.device_id, self.setting, value
        )
        await self.coordinator.async_request_refresh()


class HanetDynamicSettingSwitch(HanetSettingSwitch):
    """Control a model-specific boolean discovered at runtime."""

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting: str,
        label: str,
    ) -> None:
        digest = sha1(setting.encode("utf-8")).hexdigest()[:10]
        HanetEntity.__init__(
            self,
            coordinator,
            device_id,
            f"setting_switch_{digest}",
        )
        self.setting = setting
        self._attr_name = label
        self._attr_icon = "mdi:toggle-switch-outline"


def _looks_boolean(path: tuple[str, ...], value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {
            "true",
            "false",
            "on",
            "off",
            "enabled",
            "disabled",
        }
    if value not in {0, 1}:
        return False
    key = _canonical_path(".".join(path))
    return any(
        token in key
        for token in (
            "enable",
            "notification",
            "record",
            "detection",
            "tracking",
            "rotate",
            "reverse",
            "security",
            "led",
            "wdr",
            "mqtt",
            "rtsp",
            "audio",
            "human",
            "ptz",
        )
    )


def _canonical_path(value: str) -> str:
    return "".join(
        character for character in value.casefold() if character.isalnum()
    )
