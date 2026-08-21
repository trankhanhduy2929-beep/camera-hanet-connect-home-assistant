"""Direct HANET Cloud and native TUTK P2P client."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import logging
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ._catalog import ENDPOINTS
from ._cloud_api import HanetApiClient, endpoint_catalog
from ._errors import HanetApiError, HanetAuthError, HanetConfigurationError
from ._normalizer import (
    as_list,
    find_by_id,
    merge_device,
    normalize_department,
    normalize_device,
    normalize_event,
    normalize_person,
    normalize_place,
    unwrap,
)
from .media import MediaBridge, MjpegSubscription

_LOGGER = logging.getLogger(__name__)
_SETTINGS_TTL = 300
_MAX_MEDIA_BYTES = 24 * 1024 * 1024
_SENSITIVE_KEYS = {
    "access_token",
    "refreshtoken",
    "refresh_token",
    "password",
    "p2p_password",
    "license_key",
}


class HanetGatewayError(HanetApiError):
    """Base error exposed to the entity and service layers."""


class HanetGatewayAuthError(HanetGatewayError):
    """Cloud credentials were rejected."""


class HanetGatewayConnectionError(HanetGatewayError):
    """HANET Cloud or a direct P2P camera could not be reached."""


class HanetGatewayClient:
    """Load entities from HANET Cloud and media directly over TUTK P2P."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        api_base_url: str,
        verify_tls: bool = True,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self.username = username.strip()
        self.password = password
        self.session = session
        self.base_url = api_base_url.strip().rstrip("/")
        self.client = HanetApiClient(
            base_url=self.base_url,
            username=self.username,
            password=self.password,
            verify_tls=verify_tls,
            session=session,
        )
        self.media = MediaBridge(
            self.client,
            ffmpeg_binary=ffmpeg_binary,
        )
        self._settings_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._places: list[dict[str, Any]] = []
        self._devices: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._account: dict[str, Any] = {}

    @property
    def media_bridge_configured(self) -> bool:
        """Return whether the bundled direct P2P runtime is configured."""
        return True

    async def async_validate(self) -> dict[str, Any]:
        """Validate cloud credentials without requiring an add-on."""
        await self._cloud(self.client.authenticate(force=True))
        places = await self._load_places()
        return {"authenticated": True, "places": len(places)}

    async def async_validate_media_bridge(self) -> dict[str, Any]:
        """Validate the bundled native runtime without opening a camera."""
        status = await self.media.descriptor({"id": ""}, probe=False)
        return {
            "configured": True,
            "connected": bool(status.get("available")),
            "authenticated": bool(
                getattr(self.client, "authenticated", True)
            ),
            "error": (
                None
                if status.get("available")
                else status.get("code", "p2p_runtime_missing")
            ),
        }

    async def async_media_bridge_status(self) -> dict[str, Any]:
        """Return a non-fatal direct P2P runtime status for entities."""
        try:
            return await self.async_validate_media_bridge()
        except HanetGatewayError as err:
            return {
                "configured": self.media_bridge_configured,
                "connected": False,
                "error": str(err),
            }

    async def async_status(self) -> dict[str, Any]:
        """Return a config-flow compatible direct-cloud status."""
        result = await self.async_validate()
        return {
            "configured": bool(self.username and self.password),
            "authenticated": bool(result["authenticated"]),
            "media_bridge": self.media_bridge_configured,
        }

    async def async_state(
        self, *, force_settings: bool = False
    ) -> dict[str, Any]:
        """Build the normalized cloud snapshot used by all entity platforms."""
        await self._cloud(self.client.authenticate())
        account_result, places = await asyncio.gather(
            self._optional_endpoint("profile_get", {}),
            self._load_places(),
        )
        account = unwrap(account_result)
        self._account = dict(account) if isinstance(account, Mapping) else {}
        self._places = places
        self._devices = await self._load_devices(
            places, force_settings=force_settings
        )
        media_bridge = await self.async_media_bridge_status()
        return {
            "configured": True,
            "authenticated": True,
            "media_bridge": self.media_bridge_configured,
            "media_bridge_connected": bool(
                media_bridge.get("connected")
            ),
            "media_bridge_authenticated": bool(
                media_bridge.get("authenticated")
            ),
            "media_bridge_error": media_bridge.get("error"),
            "account": dict(self._account),
            "places": [dict(place) for place in self._places],
            "devices": [dict(device) for device in self._devices],
            "events": [dict(event) for event in self._events],
            "last_refresh": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "last_error": None,
        }

    async def _load_places(self) -> list[dict[str, Any]]:
        mobile, web = await asyncio.gather(
            self._optional_endpoint("place_list", {}),
            self._cloud(self.client.list_web_places()),
            return_exceptions=True,
        )
        if isinstance(mobile, Exception) and isinstance(web, Exception):
            raise mobile
        places: dict[str, dict[str, Any]] = {}
        for value in (
            [] if isinstance(mobile, Exception) else as_list(mobile)
        ) + ([] if isinstance(web, Exception) else list(web)):
            if not isinstance(value, Mapping):
                continue
            place = normalize_place(value)
            if place["id"]:
                places.setdefault(place["id"], _without_raw(place))
        return list(places.values())

    async def _load_devices(
        self,
        places: list[dict[str, Any]],
        *,
        force_settings: bool,
    ) -> list[dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        global_result = await self._optional_endpoint("device_list", {})
        for value in as_list(global_result):
            if isinstance(value, Mapping):
                device = normalize_device(value)
                if device["id"]:
                    normalized[device["id"]] = _without_raw(device)

        semaphore = asyncio.Semaphore(4)

        async def place_inventory(
            place: Mapping[str, Any],
        ) -> tuple[Mapping[str, Any], Any, Any]:
            async with semaphore:
                mobile, web = await asyncio.gather(
                    self._optional_endpoint(
                        "device_list", {"place_id": place["id"]}
                    ),
                    self._cloud(
                        self.client.list_web_devices(str(place["id"]))
                    ),
                    return_exceptions=True,
                )
            return place, mobile, web

        inventories = await asyncio.gather(
            *(place_inventory(place) for place in places if place.get("id"))
        )
        for place, mobile, web in inventories:
            for response in (mobile, web):
                if isinstance(response, Exception):
                    continue
                for value in as_list(response):
                    if not isinstance(value, Mapping):
                        continue
                    device = normalize_device(value, place=place)
                    if device["id"]:
                        normalized[device["id"]] = _without_raw(device)

        devices = list(normalized.values())
        await self._merge_connection_status(devices)
        await self._merge_settings(
            devices, force_settings=force_settings
        )
        return devices

    async def _merge_connection_status(
        self, devices: list[dict[str, Any]]
    ) -> None:
        if not devices:
            return
        result = await self._optional_endpoint(
            "device_all_connection_status",
            {"device_ids": [device["id"] for device in devices]},
        )
        statuses = [
            item for item in as_list(result) if isinstance(item, Mapping)
        ]
        for device in devices:
            status = find_by_id(statuses, device["id"])
            if status is None:
                continue
            device.update(_without_raw(merge_device(device, status)))

    async def _merge_settings(
        self,
        devices: list[dict[str, Any]],
        *,
        force_settings: bool,
    ) -> None:
        semaphore = asyncio.Semaphore(4)

        async def load(device: dict[str, Any]) -> None:
            device_id = str(device["id"])
            cached = self._settings_cache.get(device_id)
            if (
                cached
                and not force_settings
                and time.monotonic() - cached[0] < _SETTINGS_TTL
            ):
                device["settings"] = dict(cached[1])
                return
            async with semaphore:
                setting_result, user_result, detail_result = await asyncio.gather(
                    self._optional_endpoint(
                        "device_get_setting", {"device_id": device_id}
                    ),
                    self._optional_endpoint(
                        "device_get_user_config", {"device_id": device_id}
                    ),
                    self._optional_endpoint(
                        "device_get", {"device_id": device_id}
                    ),
                )
            settings = {}
            settings.update(_settings_mapping(setting_result))
            settings.update(_settings_mapping(user_result))
            detail = unwrap(detail_result)
            if isinstance(detail, Mapping):
                device.update(_without_raw(merge_device(device, detail)))
            device["settings"] = _safe_mapping(settings)
            self._settings_cache[device_id] = (
                time.monotonic(),
                dict(device["settings"]),
            )

        await asyncio.gather(*(load(device) for device in devices))

    async def async_events(self, *, limit: int = 250) -> list[dict[str, Any]]:
        """Return normalized recognition history directly from HANET Cloud."""
        day = datetime.now().astimezone().date().isoformat()
        places = self._places or await self._load_places()
        responses = await asyncio.gather(
            *(
                self._optional_endpoint(
                    "tracking_access_day",
                    {
                        "place_id": place["id"],
                        "Day": day,
                        "limit": min(max(int(limit), 1), 2000),
                        "offset": 0,
                    },
                )
                for place in places
            )
        )
        events: list[dict[str, Any]] = []
        seen: set[str] = set()
        for response in responses:
            for value in as_list(response):
                if not isinstance(value, Mapping):
                    continue
                event = _without_raw(
                    normalize_event(value, source="cloud")
                )
                identity = str(event.get("id") or "") or "|".join(
                    str(event.get(key) or "")
                    for key in (
                        "device_id",
                        "person_id",
                        "occurred_at",
                        "image_url",
                    )
                )
                if identity and identity in seen:
                    continue
                if identity:
                    seen.add(identity)
                events.append(event)
        events.sort(
            key=lambda item: str(
                item.get("occurred_at") or item.get("received_at") or ""
            ),
            reverse=True,
        )
        self._events = events[: min(max(int(limit), 1), 2000)]
        return [dict(event) for event in self._events]

    async def async_people(self) -> list[dict[str, Any]]:
        """Return both employees and visitors, never only the default type."""
        places = self._places or await self._load_places()
        responses = await asyncio.gather(
            *(
                self._optional_endpoint(
                    "person_list",
                    {
                        "place_id": place["id"],
                        "type": person_type,
                        "page": 1,
                        "limit": 1000,
                        "offset": 0,
                    },
                )
                for place in places
                for person_type in (0, 1)
            )
        )
        people: dict[str, dict[str, Any]] = {}
        for response in responses:
            for value in as_list(response):
                if not isinstance(value, Mapping):
                    continue
                person = _without_raw(normalize_person(value))
                if person["id"]:
                    people[person["id"]] = person
        return list(people.values())

    async def async_departments(self) -> list[dict[str, Any]]:
        """Return departments for every visible place."""
        places = self._places or await self._load_places()
        responses = await asyncio.gather(
            *(
                self._optional_endpoint(
                    "department_list",
                    {"place_id": place["id"], "limit": 1000},
                )
                for place in places
            )
        )
        departments: dict[str, dict[str, Any]] = {}
        for response in responses:
            for value in as_list(response):
                if not isinstance(value, Mapping):
                    continue
                department = _without_raw(normalize_department(value))
                if department["id"]:
                    departments[department["id"]] = department
        return list(departments.values())

    async def async_recordings(self, day: str) -> list[dict[str, Any]]:
        """Return flattened camera recording rows for one calendar day."""
        if not self._devices:
            await self.async_state()
        responses = await asyncio.gather(
            *(
                self._optional_endpoint(
                    "video_group_day",
                    {"device_id": device["id"], "Day": str(day)},
                )
                for device in self._devices
            )
        )
        clips: list[dict[str, Any]] = []
        for device, response in zip(self._devices, responses, strict=False):
            for group in as_list(response):
                if not isinstance(group, Mapping):
                    continue
                entries = group.get("entries")
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        continue
                    clips.append(
                        {
                            "id": str(
                                entry.get("event_id")
                                or entry.get("timestamp")
                                or entry.get("file")
                                or ""
                            ),
                            "device_id": str(device["id"]),
                            "device_name": device.get("name"),
                            "place_id": device.get("place_id"),
                            "place_name": device.get("place_name"),
                            "timestamp": entry.get("timestamp")
                            or group.get("time"),
                            "duration": entry.get("duration"),
                            "thumbnail_url": entry.get("thumb")
                            or entry.get("thumbnail"),
                            "file": entry.get("video") or entry.get("file"),
                        }
                    )
        return clips

    async def async_media(self, url: str) -> tuple[bytes, str]:
        """Fetch a HANET-hosted image without exposing cloud credentials."""
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not (
            (parsed.hostname or "").casefold().endswith(".hanet.ai")
            or (parsed.hostname or "").casefold() == "hanet.ai"
        ):
            raise HanetGatewayError("Media URL is outside HANET domains")
        try:
            async with self.session.get(
                str(url),
                timeout=aiohttp.ClientTimeout(total=30, connect=10),
            ) as response:
                if response.status >= 400:
                    raise HanetGatewayError(
                        f"HANET media returned HTTP {response.status}",
                        status=response.status,
                    )
                body = await response.read()
                if len(body) > _MAX_MEDIA_BYTES:
                    raise HanetGatewayError(
                        "HANET media is too large", status=413
                    )
                return body, response.content_type
        except HanetGatewayError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HanetGatewayConnectionError(
                f"Could not fetch HANET media: {type(err).__name__}"
            ) from err

    async def async_upload_face(
        self,
        *,
        fields: Mapping[str, Any],
        image: bytes,
        filename: str,
        update: bool = False,
    ) -> Any:
        """Create or update FaceID using HANET's verified `file` part."""
        endpoint = "person_update_face" if update else "person_create_face"
        content_type = (
            "image/png"
            if str(filename).casefold().endswith(".png")
            else "image/jpeg"
        )
        return await self._cloud(
            self.client.request_endpoint(
                endpoint,
                {},
                fields=fields,
                files={
                    "file": (
                        filename or "face.jpg",
                        image,
                        content_type,
                    )
                },
            )
        )

    async def async_catalog(self) -> dict[str, Any]:
        """Return the direct-cloud endpoint catalog."""
        return {"endpoints": endpoint_catalog()}

    async def async_refresh(
        self, *, settings: bool = False
    ) -> dict[str, Any]:
        """Refresh cloud state and optionally invalidate all settings."""
        if settings:
            self._settings_cache.clear()
        return await self.async_state(force_settings=settings)

    async def async_call_endpoint(
        self, endpoint: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """Call one named endpoint directly on HANET Cloud."""
        if endpoint not in ENDPOINTS:
            raise HanetGatewayError(f"Unknown HANET endpoint: {endpoint}")
        return await self._cloud(
            self.client.request_endpoint(endpoint, payload or {})
        )

    async def async_set_setting(
        self, device_id: str, setting: str, value: Any
    ) -> Any:
        """Write one known setting while preserving its cloud value type."""
        current_settings = next(
            (
                device.get("settings", {})
                for device in self._devices
                if str(device.get("id")) == str(device_id)
            ),
            {},
        )
        actual_path = _matching_path(current_settings, setting)
        current = _path_value(current_settings, actual_path)
        rendered = _preserve_type(value, current)
        payload = _setting_patch(current_settings, actual_path, rendered)
        if _canonical_key(actual_path[0]).startswith("notification"):
            result = await self.async_call_endpoint(
                "device_set_user_config",
                {
                    "device_id": device_id,
                    "config": json.dumps(
                        payload, separators=(",", ":")
                    ),
                },
            )
            read_endpoint = "device_get_user_config"
        else:
            result = await self.async_call_endpoint(
                "device_set_setting",
                {
                    "device_id": device_id,
                    "settings": json.dumps(
                        payload, separators=(",", ":")
                    ),
                },
            )
            read_endpoint = "device_get_setting"
        _ensure_mutation_success(result)
        observed: Any = None
        for attempt in range(4):
            if attempt:
                await asyncio.sleep(0.4 * attempt)
            fresh = await self.async_call_endpoint(
                read_endpoint, {"device_id": device_id}
            )
            observed = _path_value(
                _settings_mapping(fresh), actual_path
            )
            if _setting_values_equal(observed, rendered):
                break
        else:
            raise HanetGatewayError(
                "Camera khong xac nhan thay doi cai dat",
                status=409,
                code="setting_not_applied",
                payload={"setting": setting, "observed": observed},
            )
        self._settings_cache.pop(str(device_id), None)
        return result

    async def async_send_command(
        self,
        device_id: str,
        command: str,
        options: Mapping[str, Any] | None = None,
    ) -> Any:
        """Send PTZ over native P2P and other commands through HANET Cloud."""
        extra = dict(options or {})
        directions = {
            "up",
            "down",
            "left",
            "right",
            "leftUp",
            "rightUp",
            "leftDown",
            "rightDown",
            "zoomIn",
            "zoomOut",
            "autoScan",
        }
        if command not in directions | {"stop"}:
            return await self.async_call_endpoint(
                "mqtt_command",
                {
                    "device_id": device_id,
                    "command": command,
                    **extra,
                },
            )

        device = next(
            (
                item
                for item in self._devices
                if str(item.get("id") or "") == str(device_id)
            ),
            None,
        )
        if device is not None:
            try:
                return await self._cloud(
                    self.media.send_ptz(device, command)
                )
            except HanetGatewayError as err:
                _LOGGER.info(
                    "Direct HANET P2P PTZ failed for %s; trying cloud: %s",
                    device_id,
                    err,
                )

        action = "stop_ptz" if command == "stop" else "start_ptz"
        modern_payloads = [
            {
                "camera_id": device_id,
                "command": action,
                **({"direction": command} if command != "stop" else {}),
                **extra,
            },
            {
                "device_id": device_id,
                "command": action,
                **({"direction": command} if command != "stop" else {}),
                **extra,
            },
        ]
        last_error: HanetGatewayError | None = None
        for payload in modern_payloads:
            try:
                return await self.async_call_endpoint(
                    "mqtt_command", payload
                )
            except HanetGatewayError as err:
                last_error = err
                if err.status not in {400, 404, 405, 422}:
                    raise

        try:
            return await self.async_call_endpoint(
                "mqtt_command",
                {
                    "device_id": device_id,
                    "command": command,
                    **extra,
                },
            )
        except HanetGatewayError:
            if last_error is not None:
                raise last_error from None
            raise

    async def async_stream(self, device_id: str) -> dict[str, Any]:
        """Return a secret-free description of direct native P2P."""
        device = self._device(device_id)
        if device is None:
            raise HanetGatewayError("Unknown HANET camera", status=404)
        return await self._cloud(self.media.descriptor(device))

    async def async_image(self, device_id: str) -> tuple[bytes, str]:
        """Get a current direct P2P snapshot or latest event image."""
        device = self._device(device_id)
        if device is None:
            raise HanetGatewayError("Unknown HANET camera", status=404)
        with contextlib.suppress(HanetGatewayError):
            result = await self._cloud(
                self.media.snapshot(device, self._events)
            )
            if result is not None:
                return result
        event = next(
            (
                item
                for item in self._events
                if str(item.get("device_id") or "") == str(device_id)
                and item.get("image_url")
            ),
            None,
        )
        if event:
            return await self.async_media(str(event["image_url"]))
        if device and device.get("snapshot_url"):
            return await self.async_media(str(device["snapshot_url"]))
        raise HanetGatewayError("No HANET camera image is available")

    async def async_open_live(
        self, device_id: str
    ) -> tuple[MjpegSubscription, bytes]:
        """Open a native TUTK P2P stream inside Home Assistant Core."""
        device = self._device(device_id)
        if device is None:
            raise HanetGatewayError("Unknown HANET camera", status=404)
        return await self._cloud(self.media.start_mjpeg(device))

    async def async_close_live(
        self, subscription: MjpegSubscription
    ) -> None:
        """Release one direct P2P viewer."""
        await self.media.stop_mjpeg(subscription)

    async def async_close(self) -> None:
        """Close native P2P processes and the cloud client."""
        await self.media.close()
        await self.client.close()

    def _device(self, device_id: str) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self._devices
                if str(item.get("id") or "") == str(device_id)
            ),
            None,
        )

    async def _optional_endpoint(
        self, endpoint: str, payload: Mapping[str, Any]
    ) -> Any:
        try:
            return await self._cloud(
                self.client.request_endpoint(endpoint, payload)
            )
        except HanetGatewayAuthError:
            raise
        except HanetGatewayError as err:
            _LOGGER.debug("Optional HANET endpoint %s failed: %s", endpoint, err)
            return {}

    async def _cloud(self, awaitable: Any) -> Any:
        try:
            return await awaitable
        except HanetAuthError as err:
            raise HanetGatewayAuthError(
                str(err),
                status=err.status,
                code=err.code,
                field=err.field,
            ) from err
        except HanetConfigurationError as err:
            raise HanetGatewayError(str(err)) from err
        except HanetApiError as err:
            error_type = (
                HanetGatewayConnectionError
                if err.retryable
                else HanetGatewayError
            )
            raise error_type(
                str(err),
                status=err.status,
                code=err.code,
                field=err.field,
            ) from err


def _settings_mapping(value: Any) -> dict[str, Any]:
    current = unwrap(value)
    if not isinstance(current, Mapping):
        return {}
    output: dict[str, Any] = {}
    for key, item in current.items():
        if str(key).casefold() in {
            "data",
            "result",
            "response",
            "code",
            "message",
        }:
            continue
        if str(key).casefold() in {
            "setting",
            "settings",
            "config",
            "user_config",
        } and isinstance(item, Mapping):
            output.update(item)
        else:
            output[str(key)] = item
    return _safe_mapping(output)


def _safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _safe_value(item)
        for key, item in value.items()
        if _canonical_key(str(key)) not in {
            _canonical_key(item) for item in _SENSITIVE_KEYS
        }
    }


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _safe_mapping(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return value


def _without_raw(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _safe_value(item)
        for key, item in value.items()
        if key != "raw"
    }


def _matching_path(
    settings: Mapping[str, Any], requested: str
) -> tuple[str, ...]:
    current: Any = settings
    matched: list[str] = []
    for part in requested.split("."):
        actual = part
        if isinstance(current, Mapping):
            actual = next(
                (
                    str(key)
                    for key in current
                    if _canonical_key(str(key)) == _canonical_key(part)
                ),
                part,
            )
            current = current.get(actual)
        matched.append(actual)
    return tuple(matched)


def _path_value(settings: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = settings
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _setting_patch(
    settings: Mapping[str, Any],
    path: tuple[str, ...],
    value: Any,
) -> dict[str, Any]:
    if len(path) == 1:
        return {path[0]: value}
    root_value = settings.get(path[0])
    root = copy.deepcopy(root_value) if isinstance(root_value, Mapping) else {}
    cursor = root
    for part in path[1:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[path[-1]] = value
    return {path[0]: root}


def _canonical_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _preserve_type(value: Any, current: Any) -> Any:
    if isinstance(current, bool):
        if isinstance(value, str):
            return value.casefold() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(current, int) and not isinstance(current, bool):
        with contextlib.suppress(TypeError, ValueError):
            return int(value)
    if isinstance(current, float):
        with contextlib.suppress(TypeError, ValueError):
            return float(value)
    return value


def _setting_values_equal(observed: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(observed, Mapping):
            return False
        return all(
            key in observed
            and _setting_values_equal(observed[key], nested)
            for key, nested in expected.items()
        )
    if isinstance(expected, bool):
        if isinstance(observed, str):
            return observed.strip().casefold() in {
                "1" if expected else "0",
                "true" if expected else "false",
                "on" if expected else "off",
            }
        if isinstance(observed, (bool, int)):
            return bool(observed) is expected
    return observed == expected


def _ensure_mutation_success(result: Any) -> None:
    if not isinstance(result, Mapping):
        return
    failed = result.get("success") is False or result.get("ok") is False
    if isinstance(result.get("status"), bool):
        failed = failed or result["status"] is False
    code = result.get("code")
    if code is not None and str(code).strip().casefold() not in {
        "0",
        "200",
        "ok",
        "success",
    }:
        failed = True
    if failed:
        raise HanetGatewayError(
            str(
                result.get("message")
                or result.get("error")
                or "HANET tu choi thay doi"
            ),
            status=400,
            code=code,
            payload=result,
        )
