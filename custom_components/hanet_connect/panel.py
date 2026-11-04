"""Sidebar panel, websocket commands and media proxy for HANET Connect."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any
from urllib.parse import quote

import voluptuous as vol
from aiohttp import web
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_SERVICE,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .groups import ADJUSTABLE_GROUPS, GROUP_LABELS, group_recency

PANEL_URL = "hanet-connect"
PANEL_NAME = "hanet-connect-panel"
PANEL_STATIC = "/hanet_connect_static"
MEDIA_URL = "/api/hanet_connect/media"
MAX_FACE_BYTES = 6 * 1024 * 1024

_STATE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/state",
        vol.Optional("entry_id"): str,
    }
)
_FACE_CREATE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/face_create",
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
    }
)
_FACE_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/face_update",
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
        vol.Optional("alias_id"): str,
    }
)
_FACE_DELETE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/face_delete",
        vol.Optional("entry_id"): str,
        vol.Required("person_id"): str,
        vol.Optional("place_id"): str,
    }
)
_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/settings",
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
)
_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "hanet_connect/panel/refresh",
        vol.Optional("entry_id"): str,
    }
)

async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the sidebar panel, websocket API and media view once."""
    hass.http.register_view(HanetMediaView(hass))
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
        websocket_refresh,
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
    return loaded[0] if len(loaded) == 1 else None

def _error(
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    message: str,
) -> None:
    connection.send_error(msg["id"], "not_found", message)

def _event_item(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    return {
        "id": event_id,
        "kind": event.get("kind"),
        "kind_name": event.get("kind_name"),
        "person_id": event.get("person_id"),
        "person_name": event.get("person_name"),
        "device_id": event.get("device_id"),
        "device_name": event.get("device_name"),
        "place_id": event.get("place_id"),
        "place_name": event.get("place_name"),
        "occurred_at": event.get("occurred_at"),
        "has_image": bool(event.get("image_url")),
        "image": f"{MEDIA_URL}/event/{quote(event_id, safe='')}" if event_id else "",
    }

def _person_item(person: dict[str, Any]) -> dict[str, Any]:
    person_id = str(person.get("id") or "")
    return {
        "id": person_id,
        "name": person.get("name"),
        "type": person.get("type"),
        "type_name": person.get("type_name"),
        "department_id": person.get("department_id"),
        "department": person.get("department"),
        "place_id": person.get("place_id"),
        "alias_id": person.get("alias_id"),
        "enabled": person.get("enabled", True),
        "has_image": bool(person.get("image_url")),
        "image": f"{MEDIA_URL}/person/{quote(person_id, safe='')}" if person_id else "",
    }

def _snapshot(hass: HomeAssistant, entry: Any) -> dict[str, Any]:
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
            }
        )
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
        "events": [_event_item(item) for item in coordinator.events],
        "people": [_person_item(item) for item in coordinator.people],
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
    connection.send_result(msg["id"], _snapshot(hass, entry))

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
    connection.send_result(msg["id"], {"result": result, "snapshot": _snapshot(hass, entry)})

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
    fields = {"person_id": msg["person_id"], **_face_fields(msg)}
    try:
        image_value = str(msg.get("image") or "")
        if image_value:
            result = await entry.runtime_data.client.async_upload_face(
                fields=fields,
                image=_decode_image(image_value),
                filename=str(msg.get("filename") or "face.jpg"),
                update=True,
            )
        else:
            result = await entry.runtime_data.client.async_call_endpoint(
                "person_update", fields
            )
        await _after_face_change(entry)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "face_update_failed", str(err))
        return
    connection.send_result(msg["id"], {"result": result, "snapshot": _snapshot(hass, entry)})

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
    connection.send_result(msg["id"], {"result": result, "snapshot": _snapshot(hass, entry)})

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
    connection.send_result(msg["id"], _snapshot(hass, entry))

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
        user = request.get("hass_user")
        if user is not None and not user.is_admin:
            return web.Response(status=403)
        entry = self.hass.config_entries.async_entries(DOMAIN)
        for candidate in entry:
            if candidate.state is not ConfigEntryState.LOADED:
                continue
            coordinator = getattr(candidate.runtime_data, "coordinator", None)
            if coordinator is None:
                continue
            if kind == "event":
                item = next(
                    (
                        row
                        for row in coordinator.events
                        if str(row.get("id") or "") == item_id
                    ),
                    None,
                )
                image_url = item.get("image_url") if item else None
            elif kind == "person":
                person = next(
                    (
                        row
                        for row in coordinator.people
                        if str(row.get("id") or "") == item_id
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
                headers={"Cache-Control": "private, max-age=60"},
            )
        return web.Response(status=404)
