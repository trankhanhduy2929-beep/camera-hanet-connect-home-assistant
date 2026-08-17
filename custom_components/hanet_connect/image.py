"""Latest recognition image entities for HANET cameras."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import HanetConfigEntry
from .api import HanetGatewayError
from .coordinator import HanetCoordinator
from .entity import HanetEntity, setup_dynamic_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up latest event images."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[ImageEntity]:
        return [HanetLatestEventImage(coordinator, str(device["id"]))]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )

    known_people: set[str] = set()

    @callback
    def discover_people() -> None:
        entities: list[ImageEntity] = []
        for person in coordinator.people:
            person_id = str(person.get("id") or "")
            if person_id and person_id not in known_people:
                known_people.add(person_id)
                entities.append(HanetPersonImage(coordinator, person_id))
        if entities:
            async_add_entities(entities)

    discover_people()
    entry.async_on_unload(coordinator.async_add_listener(discover_people))


class HanetLatestEventImage(HanetEntity, ImageEntity):
    """Expose the latest event picture through the authenticated gateway."""

    _attr_translation_key = "latest_event_image"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: Any, device_id: str) -> None:
        HanetEntity.__init__(self, coordinator, device_id, "latest_event_image")
        ImageEntity.__init__(self, coordinator.hass, verify_ssl=True)
        self._event_id = ""

    @callback
    def _handle_coordinator_update(self) -> None:
        event_id = str(self.event.get("id") or "")
        if event_id != self._event_id:
            self._event_id = event_id
            self._attr_image_last_updated = dt_util.utcnow()
            self.__dict__.pop("image_last_updated", None)
            self.async_update_token()
        super()._handle_coordinator_update()

    @property
    def event(self) -> dict[str, Any]:
        """Return the latest camera event."""
        return self.coordinator.latest_event(self.device_id) or {}

    async def async_image(self) -> bytes | None:
        """Fetch the event image without exposing a cloud URL or gateway key."""
        image_url = self.event.get("image_url")
        if not image_url:
            return None
        try:
            body, content_type = await self.coordinator.client.async_media(
                str(image_url)
            )
        except HanetGatewayError:
            return None
        if content_type.startswith("image/"):
            self._attr_content_type = content_type
        return body


class HanetPersonImage(
    CoordinatorEntity[HanetCoordinator], ImageEntity
):
    """Expose the registered profile picture for one FaceID."""

    _attr_content_type = "image/jpeg"
    _attr_icon = "mdi:face-recognition"

    def __init__(
        self, coordinator: HanetCoordinator, person_id: str
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass, verify_ssl=True)
        self.person_id = person_id
        self._attr_has_entity_name = False
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_person_{person_id}_image"
        )
        self._current_url = ""

    @property
    def person(self) -> dict[str, Any]:
        """Return current FaceID profile metadata."""
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
        """Return a readable Vietnamese image name."""
        return f"Ảnh FaceID {self.person.get('name') or self.person_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        image_url = str(self.person.get("image_url") or "")
        if image_url != self._current_url:
            self._current_url = image_url
            self._attr_image_last_updated = dt_util.utcnow()
            self.__dict__.pop("image_last_updated", None)
            self.async_update_token()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Fetch the profile image through the authenticated client."""
        image_url = self.person.get("image_url")
        if not image_url:
            return None
        try:
            body, content_type = await self.coordinator.client.async_media(
                str(image_url)
            )
        except HanetGatewayError:
            return None
        if content_type.startswith("image/"):
            self._attr_content_type = content_type
        return body
