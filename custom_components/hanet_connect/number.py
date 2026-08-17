"""Numeric settings for HANET devices."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha1
from math import ceil
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .const import NUMBER_SETTINGS
from .coordinator import HanetCoordinator
from .entity import (
    HanetEntity,
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
    """Set up numeric controls discovered in the device response."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[NumberEntity]:
        device_id = str(device["id"])
        entities: list[NumberEntity] = [
            HanetSettingNumber(coordinator, device_id, key, limits)
            for key, limits in NUMBER_SETTINGS.items()
            if has_setting(device, key)
        ]
        known_paths = {
            _canonical_path(key)
            for key in NUMBER_SETTINGS
            if has_setting(device, key)
        }
        for path, value, label in setting_leaves(device):
            setting = ".".join(path)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or _canonical_path(setting) in known_paths
                or not setting_is_writable(path)
                or _looks_boolean_number(path, value)
            ):
                continue
            entities.append(
                HanetDynamicSettingNumber(
                    coordinator,
                    device_id,
                    setting,
                    label,
                    _number_limits(path, float(value)),
                )
            )
        return entities

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetSettingNumber(HanetEntity, NumberEntity):
    """Control a bounded numeric HANET setting."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting: str,
        limits: tuple[float, float, float],
    ) -> None:
        super().__init__(coordinator, device_id, setting)
        self.setting = setting
        self._attr_translation_key = setting
        (
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
        ) = limits

    @property
    def native_value(self) -> float | None:
        """Return the numeric value when it is parseable."""
        try:
            return float(setting_value(self.device, self.setting))
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the numeric value."""
        await self.coordinator.client.async_set_setting(
            self.device_id, self.setting, value
        )
        await self.coordinator.async_request_refresh()


class HanetDynamicSettingNumber(HanetSettingNumber):
    """Control a model-specific numeric setting discovered at runtime."""

    def __init__(
        self,
        coordinator: HanetCoordinator,
        device_id: str,
        setting: str,
        label: str,
        limits: tuple[float, float, float],
    ) -> None:
        digest = sha1(setting.encode("utf-8")).hexdigest()[:10]
        HanetEntity.__init__(
            self,
            coordinator,
            device_id,
            f"setting_number_{digest}",
        )
        self.setting = setting
        self._attr_name = label
        self._attr_icon = "mdi:tune-variant"
        (
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
        ) = limits


def _number_limits(
    path: tuple[str, ...], value: float
) -> tuple[float, float, float]:
    key = _canonical_path(".".join(path))
    step = 0.1 if not value.is_integer() else 1.0
    if any(
        token in key
        for token in (
            "volume",
            "level",
            "threshold",
            "distance",
            "sensitivity",
            "percent",
            "brightness",
        )
    ):
        return 0.0, max(100.0, ceil(value)), step
    if any(token in key for token in ("time", "interval", "duration")):
        return 0.0, max(86400.0, ceil(value)), step
    if "speed" in key:
        return 0.0, max(10.0, ceil(value)), step
    maximum = max(100.0, ceil(abs(value) * 2))
    minimum = -maximum if value < 0 else 0.0
    return minimum, maximum, step


def _looks_boolean_number(path: tuple[str, ...], value: float) -> bool:
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
