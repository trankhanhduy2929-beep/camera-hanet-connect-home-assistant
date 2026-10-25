"""Data coordinator for HANET Connect."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    HanetGatewayAuthError,
    HanetGatewayClient,
    HanetGatewayConnectionError,
    HanetGatewayError,
)
from .const import EVENT_TYPE

_LOGGER = logging.getLogger(__name__)


def _recent(occurred_at: Any, within_seconds: int) -> bool:
    """Return whether an ISO timestamp falls inside the last N seconds."""
    if not isinstance(occurred_at, str) or not occurred_at:
        return True
    try:
        moment = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (datetime.now(UTC) - moment).total_seconds() <= within_seconds


class HanetCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the add-on once and fan the same snapshot out to all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HanetGatewayClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="HANET Connect",
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.client = client
        self.entry = entry
        self._known_events: set[str] | None = None
        self._people: list[dict[str, Any]] = []
        self._departments: list[dict[str, Any]] = []
        self._metadata_refreshed_at = 0.0

    @property
    def devices(self) -> list[dict[str, Any]]:
        """Return normalized device objects."""
        if not isinstance(self.data, Mapping):
            return []
        devices = self.data.get("devices")
        if not isinstance(devices, list):
            return []
        return [dict(item) for item in devices if isinstance(item, Mapping)]

    def device(self, device_id: str) -> dict[str, Any] | None:
        """Find a device in the current snapshot."""
        wanted = str(device_id)
        return next(
            (item for item in self.devices if str(item.get("id")) == wanted), None
        )

    @property
    def events(self) -> list[dict[str, Any]]:
        """Return normalized cloud and realtime events."""
        if not isinstance(self.data, Mapping):
            return []
        events = self.data.get("events")
        if not isinstance(events, list):
            return []
        return [dict(item) for item in events if isinstance(item, Mapping)]

    def latest_event(self, device_id: str) -> dict[str, Any] | None:
        """Return the latest event associated with one camera."""
        wanted = str(device_id)
        return next(
            (
                event
                for event in self.events
                if str(event.get("device_id") or "") == wanted
            ),
            None,
        )

    def latest_identity_event(
        self, device_id: str, within_seconds: int | None = None
    ) -> dict[str, Any] | None:
        """Return the latest event tied to a recognized person."""
        return self._latest_matching(
            device_id,
            lambda event: bool(event.get("person_id"))
            or str(event.get("kind") or "").casefold() in {"employee", "visitor"},
            within_seconds,
        )

    def latest_stranger_event(
        self, device_id: str, within_seconds: int | None = None
    ) -> dict[str, Any] | None:
        """Return the latest event classified as a stranger."""
        return self._latest_matching(
            device_id,
            lambda event: str(event.get("kind") or "").casefold() == "stranger",
            within_seconds,
        )

    def latest_recognition_event(self, device_id: str) -> dict[str, Any] | None:
        """Return the latest familiar or stranger event."""
        identity = self.latest_identity_event(device_id)
        stranger = self.latest_stranger_event(device_id)
        if identity and stranger:
            if str(identity.get("occurred_at") or "") >= str(
                stranger.get("occurred_at") or ""
            ):
                return identity
            return stranger
        return identity or stranger

    def _latest_matching(
        self,
        device_id: str,
        predicate: Any,
        within_seconds: int | None,
    ) -> dict[str, Any] | None:
        wanted = str(device_id)
        for event in self.events:
            if str(event.get("device_id") or "") != wanted:
                continue
            if not predicate(event):
                continue
            if within_seconds is not None and not _recent(
                event.get("occurred_at"), within_seconds
            ):
                return None
            return event
        return None

    @property
    def people(self) -> list[dict[str, Any]]:
        """Return registered employees and visitors."""
        return [dict(item) for item in self._people]

    @property
    def departments(self) -> list[dict[str, Any]]:
        """Return employee departments."""
        return [dict(item) for item in self._departments]

    def latest_person_event(self, person_id: str) -> dict[str, Any] | None:
        """Return the latest event for one registered FaceID person."""
        wanted = str(person_id)
        return next(
            (
                event
                for event in self.events
                if str(event.get("person_id") or "") == wanted
            ),
            None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.client.async_state()
        except HanetGatewayAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (HanetGatewayConnectionError, HanetGatewayError) as err:
            raise UpdateFailed(str(err)) from err
        try:
            state["events"] = await self.client.async_events(limit=250)
        except HanetGatewayAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (HanetGatewayConnectionError, HanetGatewayError) as err:
            _LOGGER.warning("Could not refresh HANET cloud events: %s", err)
        if (
            not self._people
            or time.monotonic() - self._metadata_refreshed_at >= 300
        ):
            people, departments = await asyncio.gather(
                self.client.async_people(),
                self.client.async_departments(),
                return_exceptions=True,
            )
            if isinstance(people, list):
                self._people = people
            else:
                _LOGGER.warning("Could not refresh HANET FaceID metadata: %s", people)
            if isinstance(departments, list):
                self._departments = departments
            else:
                _LOGGER.warning(
                    "Could not refresh HANET department metadata: %s",
                    departments,
                )
            self._metadata_refreshed_at = time.monotonic()
        state["people"] = self.people
        state["departments"] = self.departments
        self._emit_new_events(state)
        return state

    def _emit_new_events(self, state: Mapping[str, Any]) -> None:
        events = state.get("events")
        if not isinstance(events, list):
            return
        rows = [item for item in events if isinstance(item, Mapping)]
        event_keys = {_event_key(item) for item in rows}
        if self._known_events is None:
            self._known_events = event_keys
            return
        if not event_keys:
            return
        for item in reversed(rows):
            if _event_key(item) not in self._known_events:
                self.hass.bus.async_fire(
                    EVENT_TYPE,
                    {"config_entry_id": self.entry.entry_id, **dict(item)},
                )
        self._known_events = event_keys


def _event_key(event: Mapping[str, Any]) -> str:
    for key in ("id", "event_id", "eventId", "uuid"):
        if event.get(key) is not None:
            return f"{key}:{event[key]}"
    return json.dumps(dict(event), sort_keys=True, default=str, separators=(",", ":"))
