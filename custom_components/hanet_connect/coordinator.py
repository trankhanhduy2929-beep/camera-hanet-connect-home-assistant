"""Data coordinator for HANET Connect."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha1
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._errors import HanetApiError
from ._normalizer import normalize_event
from .api import (
    HanetGatewayAuthError,
    HanetGatewayClient,
    HanetGatewayConnectionError,
    HanetGatewayError,
)
from .const import (
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_SERVICE,
    EVENT_TYPE,
    NOTIFY_KINDS,
)
from .groups import group_matches

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
        self._realtime_task: asyncio.Task[None] | None = None
        self._realtime_last_id: str | None = None

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

    def latest_group_event(
        self, device_id: str, group: str, within_seconds: int | None = None
    ) -> dict[str, Any] | None:
        """Return the latest event belonging to one sensor group."""
        return self._latest_matching(
            device_id,
            lambda event: group_matches(group, event),
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

    def start_realtime(self) -> None:
        """Subscribe to the HANET event stream for immediate state changes."""
        if self._realtime_task is not None and not self._realtime_task.done():
            return
        self._realtime_task = self.hass.async_create_background_task(
            self._realtime_loop(),
            "hanet_connect_event_stream",
        )

    async def async_stop_realtime(self) -> None:
        """Cancel the realtime event stream."""
        task = self._realtime_task
        self._realtime_task = None
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _realtime_loop(self) -> None:
        delay = 2
        while True:
            try:
                async for raw in self.client.async_event_stream(
                    last_event_id=self._realtime_last_id
                ):
                    if raw.get("event") == "ping":
                        continue
                    if raw.get("id"):
                        self._realtime_last_id = str(raw["id"])
                    payload = raw.get("data")
                    if not isinstance(payload, Mapping):
                        payload = {
                            "event": raw.get("event"),
                            "data": payload,
                        }
                    received_at = datetime.now(UTC).isoformat(
                        timespec="seconds"
                    )
                    rows = payload if isinstance(payload, list) else [payload]
                    for row in rows:
                        if not isinstance(row, Mapping):
                            continue
                        self._apply_realtime_event(
                            normalize_event(
                                row,
                                source="sse",
                                received_at=received_at,
                            )
                        )
                    delay = 2
            except asyncio.CancelledError:
                raise
            except HanetGatewayAuthError as err:
                _LOGGER.info("HANET event stream needs a new login: %s", err)
                await asyncio.sleep(60)
                continue
            except (HanetGatewayError, HanetApiError) as err:
                status = getattr(err, "status", None)
                if status in {401, 403}:
                    _LOGGER.debug("HANET event stream rejected credentials")
                    await asyncio.sleep(30)
                    continue
                if status in {404, 405}:
                    _LOGGER.info(
                        "HANET realtime stream is unavailable; polling only"
                    )
                    return
                _LOGGER.debug("HANET event stream disconnected: %s", err)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "HANET event stream error: %s", type(err).__name__
                )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def _apply_realtime_event(self, event: Mapping[str, Any]) -> None:
        item = dict(event)
        key = _event_key(item)
        if self._known_events is None:
            self._known_events = {_event_key(row) for row in self.events}
        if key in self._known_events:
            return
        events = [
            item,
            *(row for row in self.events if _event_key(row) != key),
        ][:250]
        data = dict(self.data) if isinstance(self.data, Mapping) else {}
        data["events"] = events
        self._known_events.add(key)
        self.data = data
        self.last_update_success = True
        self.async_update_listeners()
        self.hass.bus.async_fire(
            EVENT_TYPE,
            {"config_entry_id": self.entry.entry_id, **item},
        )
        self._notify(item)

    def _notify(self, event: Mapping[str, Any]) -> None:
        kind = str(event.get("kind") or "").casefold()
        if kind not in NOTIFY_KINDS:
            return
        titles = {
            "alarm": "Báo động",
            "employee": "Người nhà",
            "visitor": "Khách",
            "stranger": "Người lạ",
            "plate": "Biển số",
        }
        device_id = str(event.get("device_id") or "")
        device = self.device(device_id) or {}
        camera = str(
            event.get("device_name")
            or device.get("name")
            or device_id
            or ""
        ).strip()
        title = titles.get(kind, "Sự kiện HANET")
        header = f"{title} · {camera}" if camera else title
        details = [
            str(value).strip()
            for value in (
                event.get("person_name"),
                _display_time(event.get("occurred_at")),
            )
            if str(value or "").strip()
        ]
        image = str(event.get("image_url") or "").strip()
        message = " · ".join(details)
        if image:
            message = f"{message}\n{image}".strip()
        if bool(self.entry.options.get(CONF_NOTIFY_PERSISTENT, True)):
            persistent_notification.async_create(
                self.hass,
                message or title,
                title=header,
                notification_id=(
                    f"hanet_connect_{self.entry.entry_id}_"
                    f"{sha1(f'{device_id}:{kind}'.encode()).hexdigest()[:12]}"
                ),
            )
        service = self._notify_service()
        if not service:
            return
        payload: dict[str, Any] = {
            "title": header,
            "message": message or title,
        }
        if image:
            payload["data"] = {"image": image}
        self.hass.async_create_task(
            self.hass.services.async_call(
                "notify", service, payload, blocking=False
            )
        )

    def _notify_service(self) -> str:
        configured = str(
            self.entry.options.get(CONF_NOTIFY_SERVICE) or ""
        ).strip()
        if configured.startswith("notify."):
            configured = configured.removeprefix("notify.")
        if configured:
            return (
                configured
                if self.hass.services.has_service("notify", configured)
                else ""
            )
        services = self.hass.services.async_services().get("notify", {})
        mobile = sorted(
            name
            for name in services
            if name.startswith("mobile_app_")
        )
        return mobile[0] if len(mobile) == 1 else ""

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
            if _event_key(item) in self._known_events:
                continue
            self.hass.bus.async_fire(
                EVENT_TYPE,
                {"config_entry_id": self.entry.entry_id, **dict(item)},
            )
            self._notify(item)
        self._known_events.update(event_keys)
        if len(self._known_events) > 10000:
            self._known_events = set(
                list(self._known_events)[-5000:]
            )


def _event_key(event: Mapping[str, Any]) -> str:
    for key in ("id", "event_id", "eventId", "uuid"):
        if event.get(key) is not None:
            return f"{key}:{event[key]}"
    return json.dumps(dict(event), sort_keys=True, default=str, separators=(",", ":"))


def _display_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone().strftime("%H:%M %d/%m/%Y")
