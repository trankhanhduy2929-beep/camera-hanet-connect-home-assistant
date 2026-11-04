"""Sidebar panel, websocket commands and media proxy for HANET Connect."""

from __future__ import annotations

import base64
import binascii
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp
import voluptuous as vol
from aiohttp import web
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ._faceid import person_face_update_fields
from .const import (
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_SERVICE,
    DEVICE_COMMANDS,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .entity import setting_is_writable, setting_leaves
from .groups import ADJUSTABLE_GROUPS, GROUP_LABELS, group_recency

PANEL_URL = "hanet-connect"
PANEL_NAME = "hanet-connect-panel"
PANEL_STATIC = "/hanet_connect_static"
MEDIA_URL = "/api/hanet_connect/media"
MAX_FACE_BYTES = 6 * 1024 * 1024

_STATE_SCHEMA = {
    "type": "hanet_connect/panel/state",
    vol.Optional("entry_id"): str,
}
_FACE_CREATE_SCHEMA = {
    "type": "hanet_connect/panel/face_create",
    vol.Optional("entry_id"): str,
    vol.Required("place_id"): str,
    vol.Required("name"): str,
    vol.Required("image"): str,
    vol.Optional("filename", default="face.jpg"): str,
    vol.Optional("person_type", default=0): vol.All(
        vol.Coerce(int), vol.In((0, 1))
    ),
    vol.Optional("department_id", default=""): str,
    vol.Optional("alias_id", default=""): str,
    vol.Optional("sex", default=0): vol.All(vol.Coerce(int), vol.In((0, 1))),
    vol.Optional("title", default=""): str,
    vol.Optional("phone", default=""): str,
    vol.Optional("email", default=""): str,
    vol.Optional("dob", default=""): str,
}
_FACE_UPDATE_SCHEMA = {
    "type": "hanet_connect/panel/face_update",
    vol.Optional("entry_id"): str,
    vol.Required("person_id"): str,
    vol.Optional("place_id"): str,
    vol.Optional("name"): str,
    vol.Optional("image"): str,
    vol.Optional("filename", default="face.jpg"): str,
    vol.Optional("person_type"): vol.All(
        vol.Coerce(int), vol.In((0, 1))
    ),
    vol.Optional("department_id"): str,
    vol.Optional("previous_department_id"): str,
    vol.Optional("alias_id"): str,
    vol.Optional("sex"): vol.All(vol.Coerce(int), vol.In((0, 1))),
    vol.Optional("title"): str,
    vol.Optional("phone"): str,
    vol.Optional("email"): str,
    vol.Optional("dob"): str,
}
_FACE_DELETE_SCHEMA = {
    "type": "hanet_connect/panel/face_delete",
    vol.Optional("entry_id"): str,
    vol.Required("person_id"): str,
    vol.Optional("place_id"): str,
}
_SETTINGS_SCHEMA = {
    "type": "hanet_connect/panel/settings",
    vol.Optional("entry_id"): str,
    vol.Optional(CONF_NOTIFY_SERVICE): str,
    vol.Optional(CONF_NOTIFY_PERSISTENT): bool,
    **{
        vol.Optional(f"recency_{group}"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=3600)
        )
        for group in ADJUSTABLE_GROUPS
    },
}
_REFRESH_SCHEMA = {
    "type": "hanet_connect/panel/refresh",
    vol.Optional("entry_id"): str,
}
_EVENTS_SCHEMA = {
    "type": "hanet_connect/panel/events",
    vol.Optional("entry_id"): str,
    vol.Optional("day"): str,
    vol.Optional("device_id"): str,
    vol.Optional("limit", default=2000): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=2000)
    ),
}
_RECORDINGS_SCHEMA = {
    "type": "hanet_connect/panel/recordings",
    vol.Optional("entry_id"): str,
    vol.Optional("day"): str,
    vol.Optional("device_id"): str,
    vol.Optional("source", default="cloud"): vol.In(("cloud",)),
}
_COMMAND_SCHEMA = {
    "type": "hanet_connect/panel/command",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): str,
    vol.Required("command"): vol.In(DEVICE_COMMANDS),
    vol.Optional("options", default={}): dict,
}
_SETTING_SCHEMA = {
    "type": "hanet_connect/panel/setting",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): str,
    vol.Required("setting"): str,
    vol.Required("value"): object,
}

_CLIP_CACHE_TTL = 30
_CLIP_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
_EVENT_MEDIA_TTL = 3600
_EVENT_MEDIA_CACHE: dict[str, tuple[float, str]] = {}

async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the sidebar panel, websocket API and media views once."""
    hass.http.register_view(HanetMediaView(hass))
    hass.http.register_view(HanetClipThumbView(hass))
    hass.http.register_view(HanetRecordingView(hass))
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                PANEL_STATIC,
                str(Path(__file__).parent / "frontend"),
                False,
            )
        ]
    )
    frontend.async_register_built_in_panel(
        hass,
        "custom",
        sidebar_title="HANET Connect",
        sidebar_icon="mdi:cctv",
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": PANEL_NAME,
                "module_url": f"{PANEL_STATIC}/panel.js?v={INTEGRATION_VERSION}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
        require_admin=True,
    )
    for handler in (
        websocket_state,
        websocket_face_create,
        websocket_face_update,
        websocket_face_delete,
        websocket_settings,
        websocket_command,
        websocket_setting,
        websocket_refresh,
        websocket_events,
        websocket_recordings,
    ):
        websocket_api.async_register_command(hass, handler)

def _entry_for_msg(hass: HomeAssistant, msg: dict[str, Any]) -> Any:
    wanted = str(msg.get("entry_id") or "")
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and getattr(entry.runtime_data, "coordinator", None) is not None
    ]
    if wanted:
        for entry in loaded:
            if entry.entry_id == wanted:
                return entry
        return None
    return loaded[0] if loaded else None

def _error(
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    message: str,
) -> None:
    connection.send_error(msg["id"], "not_found", message)

def _remember_event_images(events: list[dict[str, Any]]) -> None:
    now = time.monotonic()
    for event in events:
        image_url = str(event.get("image_url") or "")
        identity = _event_identity(event)
        if identity and image_url:
            _EVENT_MEDIA_CACHE[identity] = (now, image_url)
    if len(_EVENT_MEDIA_CACHE) > 2000:
        cutoff = now - _EVENT_MEDIA_TTL
        for key, (stamp, _) in list(_EVENT_MEDIA_CACHE.items()):
            if stamp < cutoff:
                _EVENT_MEDIA_CACHE.pop(key, None)

def _item_key(value: str) -> str:
    """Encode an opaque item id so it is safe in one URL path segment."""
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_item_key(value: str) -> str:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return value


def _media_signer(hass: HomeAssistant, connection: Any) -> Any:
    """Build a signer for image and clip URLs on one websocket connection."""
    refresh_token_id = getattr(connection, "refresh_token_id", None)

    def sign(path: str) -> str:
        if not path:
            return ""
        return async_sign_path(
            hass,
            path,
            timedelta(hours=1),
            refresh_token_id=refresh_token_id,
        )

    return sign

def _event_item(
    event: dict[str, Any], sign: Any = None
) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    image_key = _item_key(event_id or _event_identity(event)) if event.get("image_url") else ""
    image = f"{MEDIA_URL}/event/{image_key}" if image_key else ""
    return {
        "id": event_id,
        "kind": event.get("kind"),
        "kind_name": event.get("kind_name"),
        "source": event.get("source"),
        "recognized": bool(event.get("recognized")),
        "person_id": event.get("person_id"),
        "person_name": event.get("person_name"),
        "person_title": event.get("person_title"),
        "title": event.get("title"),
        "device_id": event.get("device_id"),
        "device_name": event.get("device_name"),
        "place_id": event.get("place_id"),
        "place_name": event.get("place_name"),
        "occurred_at": event.get("occurred_at"),
        "received_at": event.get("received_at"),
        "has_image": bool(event.get("image_url")),
        "image": sign(image) if sign else image,
    }


def _person_item(person: dict[str, Any], sign: Any = None) -> dict[str, Any]:
    person_id = str(person.get("id") or "")
    return {
        "id": person_id,
        "name": person.get("name"),
        "type": person.get("type"),
        "type_name": person.get("type_name"),
        "sex": person.get("sex"),
        "title": person.get("title"),
        "phone": person.get("phone"),
        "email": person.get("email"),
        "dob": person.get("dob"),
        "department_id": person.get("department_id"),
        "department": person.get("department"),
        "place_id": person.get("place_id"),
        "alias_id": person.get("alias_id"),
        "enabled": person.get("enabled", True),
        "has_image": bool(person.get("image_url")),
        "image": (
            sign(f"{MEDIA_URL}/person/{_item_key(person_id)}")
            if sign and person_id
            else f"{MEDIA_URL}/person/{_item_key(person_id)}" if person_id else ""
        ),
    }


def _clip_item(
    clip: dict[str, Any], day: str, sign: Any = None
) -> dict[str, Any]:
    device_id = str(clip.get("device_id") or "")
    file_path = str(clip.get("file") or "")
    files = {"device_id": device_id, "file": file_path, "day": day}
    playback = f"{MEDIA_URL}/recording?{urlencode(files)}" if device_id and file_path else ""
    thumbnail = (
        f"{MEDIA_URL}/clip?{urlencode(files)}"
        if device_id and file_path and clip.get("thumbnail_url")
        else ""
    )
    return {
        "id": str(clip.get("id") or file_path),
        "event_id": clip.get("event_id"),
        "device_id": device_id,
        "device_name": clip.get("device_name"),
        "place_id": clip.get("place_id"),
        "place_name": clip.get("place_name"),
        "timestamp": clip.get("timestamp"),
        "duration": clip.get("duration"),
        "day": day,
        "source": "cloud",
        "thumbnail": sign(thumbnail) if sign else thumbnail,
        "playback": sign(playback) if sign else playback,
        "download": (
            sign(f"{playback}&download=1") if sign and playback
            else f"{playback}&download=1" if playback else ""
        ),
        "has_file": bool(file_path),
    }

_SETTING_GROUPS = (
    (
        "Hình ảnh & âm thanh",
        (
            "led",
            "wdr",
            "ir",
            "reverse",
            "rotate",
            "audio",
            "volume",
            "resolution",
            "quality",
            "brightness",
            "flip",
        ),
    ),
    (
        "Nhận diện",
        (
            "human",
            "recognition",
            "detection",
            "fall",
            "pet",
            "distance",
            "threshold",
            "biopsy",
            "tracking",
            "face",
        ),
    ),
    (
        "Ghi hình & cảnh báo",
        ("record", "alarm", "sound", "security", "storage", "sd", "siren", "alert"),
    ),
    ("Thông báo", ("notification", "notify")),
    ("PTZ", ("ptz", "scan", "preset", "zoom")),
)
_SETTING_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "quality": (("480p", "480p"), ("720p", "720p"), ("1080p", "1080p"), ("1440p", "2K")),
    "resolution": (("1", "480p"), ("2", "720p"), ("3", "1080p"), ("4", "2K")),
    "storage": (("off", "Tắt"), ("sd", "Thẻ SD"), ("cloud", "Cloud")),
    "recognitionarea": (
        ("full", "Toàn khung"),
        ("center_half", "Giữa 1/2"),
        ("center_third", "Giữa 1/3"),
    ),
}
_DESTRUCTIVE_SETTING_WORDS = (
    "reset",
    "reboot",
    "restart",
    "format",
    "factory",
    "upgrade",
)
_BOOLEAN_SETTING_WORDS = (
    "enable",
    "enabled",
    "notification",
    "record",
    "detection",
    "tracking",
    "reverse",
    "security",
    "led",
    "wdr",
    "ir",
    "mqtt",
    "rtsp",
    "audio",
    "human",
    "ptz",
    "rotate",
    "sound",
    "alarm",
)


def _canonical(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _setting_kind(key: str, value: Any) -> str:
    canonical = _canonical(key)
    if canonical in _SETTING_OPTIONS:
        return "select"
    if isinstance(value, bool):
        return "boolean"
    boolean_word = str(value).strip().casefold()
    if (
        any(word in canonical for word in _BOOLEAN_SETTING_WORDS)
        and boolean_word in {"0", "1", "true", "false", "on", "off"}
    ):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        try:
            float(value)
        except ValueError:
            return "text"
        return "number"
    return "text"


def _setting_group(key: str) -> str:
    canonical = _canonical(key)
    for label, words in _SETTING_GROUPS:
        if any(word in canonical for word in words):
            return label
    return "Khác"


def _device_settings(device: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, value, label in setting_leaves(device):
        if not setting_is_writable(path):
            continue
        key = ".".join(path)
        canonical = _canonical(key)
        if canonical in seen or any(
            word in canonical for word in _DESTRUCTIVE_SETTING_WORDS
        ):
            continue
        seen.add(canonical)
        kind = _setting_kind(key, value)
        row: dict[str, Any] = {
            "key": key,
            "label": label,
            "value": value,
            "kind": kind,
            "group": _setting_group(key),
        }
        options = _SETTING_OPTIONS.get(canonical)
        if options:
            row["options"] = [{"value": value, "label": text} for value, text in options]
        rows.append(row)
    order = {label: index for index, (label, _) in enumerate(_SETTING_GROUPS)}
    rows.sort(key=lambda item: (order.get(item["group"], len(order)), item["label"]))
    return rows


def _snapshot(
    hass: HomeAssistant, entry: Any, sign: Any = None
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    options = entry.options
    registry = er.async_get(hass)
    cameras = {
        item.unique_id: item.entity_id
        for item in registry.entities.values()
        if item.config_entry_id == entry.entry_id and item.domain == "camera"
    }
    devices = []
    for device in coordinator.devices:
        device_id = str(device.get("id") or "")
        cameras_for = [
            entity_id
            for unique_id, entity_id in cameras.items()
            if unique_id.endswith(f"_{device_id}_camera")
        ]
        devices.append(
            {
                "id": device_id,
                "name": device.get("name"),
                "model": device.get("model"),
                "serial": device.get("serial"),
                "firmware": device.get("firmware"),
                "online": bool(device.get("online")),
                "place_id": device.get("place_id"),
                "place_name": device.get("place_name"),
                "camera_entity": cameras_for[0] if cameras_for else "",
                "settings": _device_settings(device),
            }
        )
    people = [_person_item(item, sign) for item in coordinator.people]
    places: dict[str, str] = {}
    for device in devices:
        if device["place_id"]:
            places[str(device["place_id"])] = device["place_name"] or "Địa điểm"
    for person in people:
        if person.get("place_id"):
            places.setdefault(str(person["place_id"]), f"Địa điểm {person['place_id']}")
    return {
        "entry_id": entry.entry_id,
        "entry_title": entry.title,
        "status": {
            "transport": getattr(coordinator, "event_transport", ""),
            "last_event_at": getattr(coordinator, "last_event_at", None),
            "latency_seconds": getattr(coordinator, "last_event_latency", None),
            "online": sum(1 for item in devices if item["online"]),
            "devices": len(devices),
            "events": len(coordinator.events),
            "people": len(coordinator.people),
        },
        "devices": devices,
        "places": [
            {"id": place_id, "name": name}
            for place_id, name in sorted(places.items(), key=lambda item: item[1])
        ],
        "events": [_event_item(item, sign) for item in coordinator.events],
        "people": people,
        "departments": [
            {
                "id": str(item.get("id") or ""),
                "name": item.get("name"),
            }
            for item in coordinator.departments
        ],
        "groups": [
            {"group": group, "label": GROUP_LABELS.get(group, group)}
            for group in ADJUSTABLE_GROUPS
        ],
        "settings": {
            "notify_service": options.get(CONF_NOTIFY_SERVICE, ""),
            "notify_persistent": bool(
                options.get(CONF_NOTIFY_PERSISTENT, True)
            ),
            **{
                f"recency_{group}": group_recency(group, options)
                for group in ADJUSTABLE_GROUPS
            },
        },
    }

@websocket_api.websocket_command(_STATE_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the panel snapshot."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    connection.send_result(
        msg["id"], _snapshot(hass, entry, _media_signer(hass, connection))
    )

def _decode_image(value: str) -> bytes:
    encoded = value.strip()
    if encoded.startswith("data:"):
        _, separator, encoded = encoded.partition(",")
        if not separator:
            raise ValueError("Invalid image data URL")
    try:
        image = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ValueError("Invalid base64 image") from err
    if not image:
        raise ValueError("Face image is empty")
    if len(image) > MAX_FACE_BYTES:
        raise ValueError("Face image is too large")
    return image

def _face_fields(msg: dict[str, Any]) -> dict[str, Any]:
    name = msg.get("name")
    return {
        key: value
        for key, value in {
            "place_id": msg.get("place_id"),
            "name": name,
            "person_name": name,
            "type": msg.get("person_type"),
            "alias_id": msg.get("alias_id"),
            "department_id": msg.get("department_id"),
            "sex": msg.get("sex"),
            "title": msg.get("title"),
            "phone": msg.get("phone"),
            "email": msg.get("email"),
            "dob": msg.get("dob"),
        }.items()
        if value not in (None, "")
    }

async def _after_face_change(entry: Any) -> None:
    coordinator = entry.runtime_data.coordinator
    coordinator._metadata_refreshed_at = 0
    await coordinator.async_request_refresh()

@websocket_api.websocket_command(_FACE_CREATE_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_face_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a FaceID from a browser upload."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    try:
        image = _decode_image(msg["image"])
        result = await entry.runtime_data.client.async_upload_face(
            fields=_face_fields(msg),
            image=image,
            filename=str(msg.get("filename") or "face.jpg"),
        )
        await _after_face_change(entry)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "face_create_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "result": result,
            "snapshot": _snapshot(hass, entry, _media_signer(hass, connection)),
        },
    )

@websocket_api.websocket_command(_FACE_UPDATE_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_face_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update FaceID metadata and optionally replace its photo."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    try:
        result = await entry.runtime_data.client.async_update_face_profile(msg)
        image_value = str(msg.get("image") or "")
        if image_value:
            face_fields = person_face_update_fields(msg)
            if not face_fields.get("place_id"):
                raise ValueError("Cần địa điểm để cập nhật ảnh FaceID")
            await entry.runtime_data.client.async_upload_face(
                fields=face_fields,
                image=_decode_image(image_value),
                filename=str(msg.get("filename") or "face.jpg"),
                update=True,
            )
        await _after_face_change(entry)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "face_update_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "result": result,
            "snapshot": _snapshot(hass, entry, _media_signer(hass, connection)),
        },
    )

@websocket_api.websocket_command(_FACE_DELETE_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_face_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete one FaceID."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    payload = {
        key: msg[key]
        for key in ("person_id", "place_id")
        if msg.get(key)
    }
    try:
        result = await entry.runtime_data.client.async_call_endpoint(
            "person_delete", payload
        )
        await _after_face_change(entry)
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "face_delete_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "result": result,
            "snapshot": _snapshot(hass, entry, _media_signer(hass, connection)),
        },
    )

def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _event_identity(event: dict[str, Any]) -> str:
    return str(event.get("id") or "") or "|".join(
        str(event.get(key) or "")
        for key in ("device_id", "person_id", "occurred_at", "image_url")
    )


def _merge_events(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in [*primary, *secondary]:
        identity = _event_identity(event)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        merged.append(event)
    merged.sort(
        key=lambda item: str(item.get("occurred_at") or item.get("received_at") or ""),
        reverse=True,
    )
    return merged


async def _cached_recordings(entry: Any, day: str) -> list[dict[str, Any]]:
    key = (str(entry.entry_id), day)
    cached = _CLIP_CACHE.get(key)
    if cached and time.monotonic() - cached[0] < _CLIP_CACHE_TTL:
        return [dict(clip) for clip in cached[1]]
    clips = await entry.runtime_data.client.async_recordings(day)
    clips.sort(
        key=lambda clip: str(clip.get("timestamp") or ""),
        reverse=True,
    )
    _CLIP_CACHE[key] = (time.monotonic(), [dict(clip) for clip in clips])
    return [dict(clip) for clip in clips]


@websocket_api.websocket_command(_EVENTS_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return normalized events for one day without exposing cloud URLs."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    day = str(msg.get("day") or _today())
    try:
        rows = await entry.runtime_data.client.async_events(
            limit=int(msg.get("limit") or 2000), day=day
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "events_failed", str(err))
        return
    events = rows
    if day == _today():
        events = _merge_events(entry.runtime_data.coordinator.events, rows)
    device_id = str(msg.get("device_id") or "")
    if device_id:
        events = [
            event
            for event in events
            if str(event.get("device_id") or "") == device_id
        ]
    _remember_event_images(events)
    connection.send_result(
        msg["id"],
        {
            "day": day,
            "events": [
                _event_item(event, _media_signer(hass, connection)) for event in events
            ],
        },
    )


@websocket_api.websocket_command(_RECORDINGS_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_recordings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return cloud recording clips for one day."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    day = str(msg.get("day") or _today())
    try:
        clips = await _cached_recordings(entry, day)
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "recordings_failed", str(err))
        return
    device_id = str(msg.get("device_id") or "")
    if device_id:
        clips = [
            clip
            for clip in clips
            if str(clip.get("device_id") or "") == device_id
        ]
    connection.send_result(
        msg["id"],
        {
            "day": day,
            "source": "cloud",
            "clips": [
                _clip_item(clip, day, _media_signer(hass, connection)) for clip in clips
            ],
        },
    )


@websocket_api.websocket_command(_SETTINGS_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update recognition windows and notification options."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    options = dict(entry.options)
    for key in (
        CONF_NOTIFY_SERVICE,
        CONF_NOTIFY_PERSISTENT,
        *(f"recency_{group}" for group in ADJUSTABLE_GROUPS),
    ):
        if key in msg:
            options[key] = msg[key]
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], {"ok": True})

@websocket_api.websocket_command(_COMMAND_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_command(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send one supported camera command."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    try:
        result = await entry.runtime_data.client.async_send_command(
            str(msg["device_id"]),
            str(msg["command"]),
            msg.get("options") or {},
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "command_failed", str(err))
        return
    connection.send_result(msg["id"], {"result": result})

@websocket_api.websocket_command(_SETTING_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_setting(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Write one camera setting and return the refreshed snapshot."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    try:
        result = await entry.runtime_data.client.async_set_setting(
            str(msg["device_id"]),
            str(msg["setting"]),
            msg["value"],
        )
        await entry.runtime_data.coordinator.async_refresh()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "setting_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "result": result,
            "snapshot": _snapshot(hass, entry, _media_signer(hass, connection)),
        },
    )

@websocket_api.websocket_command(_REFRESH_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_refresh(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Refresh HANET cloud data for the panel."""
    entry = _entry_for_msg(hass, msg)
    if entry is None:
        _error(connection, msg, "No loaded HANET Connect entry")
        return
    await entry.runtime_data.coordinator.async_request_refresh()
    connection.send_result(
        msg["id"], _snapshot(hass, entry, _media_signer(hass, connection))
    )

def _admin_request(request: web.Request) -> bool:
    user = request.get("hass_user")
    return user is None or bool(user.is_admin)


def _loaded_entries(hass: HomeAssistant) -> list[Any]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and getattr(entry.runtime_data, "coordinator", None) is not None
    ]


class HanetMediaView(HomeAssistantView):
    """Proxy event and FaceID images without exposing HANET URLs."""

    url = MEDIA_URL + "/{kind}/{item_id}"
    name = "api:hanet_connect:media"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, kind: str, item_id: str
    ) -> web.Response:
        """Return one authenticated image."""
        if not _admin_request(request):
            return web.Response(status=403)
        wanted = _decode_item_key(item_id)
        for candidate in _loaded_entries(self.hass):
            coordinator = candidate.runtime_data.coordinator
            if kind == "event":
                cached = _EVENT_MEDIA_CACHE.get(wanted)
                if cached and time.monotonic() - cached[0] < _EVENT_MEDIA_TTL:
                    image_url = cached[1]
                else:
                    item = next(
                        (
                            row
                            for row in coordinator.events
                            if str(row.get("id") or "") == wanted
                            or _event_identity(row) == wanted
                        ),
                        None,
                    )
                    image_url = item.get("image_url") if item else None
            elif kind == "person":
                person = next(
                    (
                        row
                        for row in coordinator.people
                        if str(row.get("id") or "") == wanted
                    ),
                    None,
                )
                image_url = person.get("image_url") if person else None
            else:
                image_url = None
            if not image_url:
                continue
            try:
                body, content_type = await candidate.runtime_data.client.async_media(
                    str(image_url)
                )
            except Exception:  # noqa: BLE001
                return web.Response(status=502)
            return web.Response(
                body=body,
                content_type=content_type or "image/jpeg",
                headers={"Cache-Control": "private, max-age=120"},
            )
        return web.Response(status=404)


class HanetClipThumbView(HomeAssistantView):
    """Proxy Cloud recording thumbnails through Home Assistant authentication."""

    url = MEDIA_URL + "/clip"
    name = "api:hanet_connect:media_clip"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the thumbnail for one cloud clip."""
        if not _admin_request(request):
            return web.Response(status=403)
        device_id = str(request.query.get("device_id") or "")
        file_path = str(request.query.get("file") or "")
        day = str(request.query.get("day") or _today())
        if not device_id or not file_path:
            return web.Response(status=400)
        for candidate in _loaded_entries(self.hass):
            try:
                clips = await _cached_recordings(candidate, day)
            except Exception:  # noqa: BLE001
                continue
            clip = next(
                (
                    item
                    for item in clips
                    if str(item.get("device_id") or "") == device_id
                    and str(item.get("file") or "") == file_path
                ),
                None,
            )
            thumbnail = clip.get("thumbnail_url") if clip else None
            if not thumbnail:
                continue
            try:
                body, content_type = await candidate.runtime_data.client.async_media(
                    str(thumbnail)
                )
            except Exception:  # noqa: BLE001
                return web.Response(status=502)
            return web.Response(
                body=body,
                content_type=content_type or "image/jpeg",
                headers={"Cache-Control": "private, max-age=120"},
            )
        return web.Response(status=404)


class HanetRecordingView(HomeAssistantView):
    """Stream a Cloud recording without exposing its signed HANET URL."""

    url = MEDIA_URL + "/recording"
    name = "api:hanet_connect:media_recording"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Proxy one cloud clip, forwarding browser Range requests."""
        if not _admin_request(request):
            return web.Response(status=403)
        device_id = str(request.query.get("device_id") or "")
        file_path = str(request.query.get("file") or "")
        if (
            not device_id
            or not file_path.startswith(f"/{device_id}/")
            or not file_path.lower().endswith(".mp4")
            or ".." in file_path
        ):
            return web.Response(status=400)
        for candidate in _loaded_entries(self.hass):
            client = candidate.runtime_data.client
            try:
                upstream_url = await client.async_recording_url(device_id, file_path)
            except Exception:  # noqa: BLE001
                continue
            headers = {}
            requested_range = request.headers.get("Range")
            if requested_range:
                headers["Range"] = requested_range
            timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_read=60)
            try:
                upstream = await client.session.get(
                    upstream_url, headers=headers, timeout=timeout
                )
            except (aiohttp.ClientError, TimeoutError):
                return web.Response(status=502)
            async with upstream:
                if upstream.status >= 400:
                    return web.Response(status=502)
                response_headers = {}
                for header in (
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                ):
                    value = upstream.headers.get(header)
                    if value:
                        response_headers[header] = value
                if "Content-Type" not in response_headers:
                    response_headers["Content-Type"] = "video/mp4"
                response_headers.setdefault("Cache-Control", "private, max-age=300")
                if str(request.query.get("download") or "") in {
                    "1",
                    "true",
                    "yes",
                }:
                    filename = file_path.rsplit("/", 1)[-1] or "hanet-clip.mp4"
                    response_headers["Content-Disposition"] = (
                        f'attachment; filename="{filename}"'
                    )
                response = web.StreamResponse(
                    status=upstream.status,
                    headers=response_headers,
                )
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    await response.write(chunk)
                await response.write_eof()
                return response
        return web.Response(status=404)
