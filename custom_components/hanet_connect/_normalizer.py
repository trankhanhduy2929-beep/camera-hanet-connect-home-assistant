"""Normalize loosely documented HANET response objects."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

WRAPPER_KEYS = ("data", "result", "payload", "response")
LIST_KEYS = (
    "items",
    "list",
    "rows",
    "records",
    "places",
    "locations",
    "devices",
    "cameras",
    "persons",
    "events",
    "license_plates",
)

EVENT_KIND_BY_CODE = {
    0: "employee",
    1: "visitor",
    2: "stranger",
    3: "alarm",
    4: "human",
}
EVENT_KIND_NAMES = {
    "employee": "Nhân viên",
    "visitor": "Khách",
    "stranger": "Người lạ",
    "alarm": "Cảnh báo",
    "human": "Phát hiện người",
    "plate": "Biển số",
    "checkin": "Chấm công",
    "face": "Khuôn mặt",
}


def unwrap(value: Any) -> Any:
    """Remove common API envelope objects without discarding metadata lists."""
    current = value
    seen: set[int] = set()
    while isinstance(current, Mapping) and id(current) not in seen:
        seen.add(id(current))
        for key in WRAPPER_KEYS:
            nested = current.get(key)
            if nested is not None:
                current = nested
                break
        else:
            return current
    return current


def as_list(value: Any) -> list[Any]:
    """Find the primary list in a HANET response."""
    current = unwrap(value)
    if isinstance(current, list):
        return current
    if isinstance(current, tuple):
        return list(current)
    if isinstance(current, Mapping):
        for key in LIST_KEYS:
            nested = current.get(key)
            if isinstance(nested, (list, tuple)):
                return list(nested)
        for nested in current.values():
            if isinstance(nested, list):
                return nested
    return []


def pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-null key."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def pick_loose(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Pick a value while tolerating camelCase and legacy API key casing."""
    value = pick(mapping, *keys)
    if value is not None:
        return value
    wanted = {_canonical_key(key) for key in keys}
    for key, candidate in mapping.items():
        if candidate is not None and _canonical_key(str(key)) in wanted:
            return candidate
    return default


def flatten_mapping(value: Any) -> dict[str, Any]:
    """Flatten only nested setting/config envelope objects."""
    if not isinstance(value, Mapping):
        return {}
    output: dict[str, Any] = dict(value)
    for key in ("setting", "settings", "config", "user_config", "features", "device_features"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            output.update(nested)
    return output


def to_bool(value: Any, *, default: bool = False) -> bool:
    """Interpret status values returned as booleans, numbers or text."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "online", "connected", "active", "enabled"}:
            return True
        if normalized in {
            "0",
            "false",
            "no",
            "off",
            "offline",
            "disconnected",
            "inactive",
            "disabled",
        }:
            return False
    return default


def normalize_place(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a place/location object."""
    place_id = pick(raw, "id", "place_id", "placeId", "location_id", "locationId", "uuid")
    return {
        "id": str(place_id) if place_id is not None else "",
        "name": str(pick(raw, "name", "place_name", "placeName", "location_name", default="HANET")),
        "type": pick(raw, "type", "place_type", "placeType"),
        "role": pick(raw, "role", "permission", "user_role"),
        "raw": dict(raw),
    }


def _extract_media(raw: Mapping[str, Any]) -> dict[str, Any]:
    flat = flatten_mapping(raw)
    return {
        "stream_url": pick(
            flat,
            "stream_url",
            "streamUrl",
            "streamurl",
            "video_url",
            "videoUrl",
            "rtsp_url",
            "rtspUrl",
        ),
        "snapshot_url": pick(
            flat,
            "snapshot_url",
            "snapshotUrl",
            "thumbnail",
            "thumbnail_url",
            "thumb_url",
            "image_url",
            "imageUrl",
            "avatar",
        ),
        "peer_id": pick(flat, "peer_id", "peerId"),
        "p2p_id": pick(flat, "p2p_id", "p2pId", "uid"),
    }


def normalize_device(
    raw: Mapping[str, Any], *, place: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Normalize a camera/access device while preserving the full response."""
    flat = flatten_mapping(raw)
    device_id = pick(raw, "id", "device_id", "deviceId", "camera_id", "cameraId", "serial", "uuid")
    place_id = pick(raw, "place_id", "placeId", "location_id", "locationId")
    place_name = pick(raw, "place_name", "placeName", "location_name", "locationName")
    if place:
        place_id = place_id or place.get("id")
        place_name = place_name or place.get("name")
    status_value = pick(
        raw,
        "online",
        "is_online",
        "isOnline",
        "is_active",
        "isActive",
        "connected",
        "connection_status",
        "connectionStatus",
        "status",
    )
    firmware = pick(flat, "firmware_version", "firmwareVersion", "firmware", "version")
    latest = pick(flat, "firmware_latest", "latest_firmware", "latestFirmware")
    media = _extract_media(raw)
    return {
        "id": str(device_id) if device_id is not None else "",
        "name": str(
            pick(
                raw,
                "name",
                "device_name",
                "deviceName",
                "camera_name",
                default=device_id or "HANET",
            )
        ),
        "model": pick(
            raw,
            "model",
            "device_model",
            "deviceModel",
            "device_type",
            "deviceType",
            "type",
        ),
        "serial": pick(raw, "serial", "serial_number", "serialNumber", default=device_id),
        "place_id": str(place_id) if place_id is not None else "",
        "place_name": place_name,
        "online": to_bool(status_value),
        "status": status_value,
        "firmware": firmware,
        "latest_firmware": latest,
        "features": flatten_mapping(pick(raw, "features", "device_features", default={})),
        "settings": flatten_mapping(
            pick(raw, "settings", "setting", "config", "user_config", default={})
        ),
        **media,
        "raw": dict(raw),
    }


def normalize_person(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return the person fields needed by the app-like Face ID view."""
    person_id = pick_loose(raw, "person_id", "personId", "id", "face_id", "faceId")
    first_name = str(pick_loose(raw, "first_name", "firstName", default="") or "").strip()
    last_name = str(pick_loose(raw, "last_name", "lastName", default="") or "").strip()
    name = str(pick_loose(raw, "name", "person_name", "personName", default="") or "").strip()
    if not name:
        name = " ".join(part for part in (first_name, last_name) if part).strip()
    return {
        "id": str(person_id) if person_id is not None else "",
        "name": name or "Face ID",
        "image_url": pick_loose(
            raw,
            "image",
            "image_url",
            "imageUrl",
            "avatar",
            "avatar_url",
            "avatarUrl",
            "photo",
        ),
        "type": pick_loose(raw, "type", "person_type", "personType", "customer_type"),
        "type_name": pick_loose(
            raw, "type_name", "typeName", "person_title", "personTitle", "title"
        ),
        "sub_type": pick_loose(raw, "sub_type", "subType"),
        "sub_type_name": pick_loose(raw, "sub_type_name", "subTypeName"),
        "place_id": _string_id(
            pick_loose(raw, "place_id", "placeId", "placeID")
        ),
        "department_id": _string_id(
            pick_loose(raw, "department_id", "departmentId")
        ),
        "department": pick_loose(raw, "department_name", "departmentName"),
        "alias_id": pick_loose(raw, "alias_id", "aliasID", "custom_id", "customId"),
        "phone": pick_loose(raw, "phone", "phone_number", "phoneNumber"),
        "email": pick_loose(raw, "email"),
        "enabled": to_bool(pick_loose(raw, "enable", "enabled", "active"), default=True),
        "created_at": pick_loose(raw, "created_at", "createdAt"),
        "raw": dict(raw),
    }


def normalize_department(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable department fields for employee management."""
    department_id = pick_loose(raw, "department_id", "departmentId", "id")
    return {
        "id": _string_id(department_id),
        "name": str(
            pick_loose(
                raw,
                "department_name",
                "departmentName",
                "name",
                default="Phòng ban",
            )
        ),
        "place_id": _string_id(
            pick_loose(raw, "place_id", "placeId", "placeID")
        ),
        "person_count": pick_loose(
            raw,
            "person_count",
            "personCount",
            "total_person",
            "total",
            default=0,
        ),
        "created_at": pick_loose(raw, "created_at", "createdAt"),
        "raw": dict(raw),
    }


def normalize_plate(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return readable license plate fields while retaining the cloud object."""
    plate_id = pick_loose(raw, "license_plate_id", "licensePlateId", "plate_id", "id")
    return {
        "id": str(plate_id) if plate_id is not None else "",
        "number": str(
            pick_loose(
                raw,
                "license_plate",
                "licensePlate",
                "plate_number",
                "plateNumber",
                "number",
                default="",
            )
            or ""
        ),
        "name": pick_loose(raw, "name", "owner_name", "ownerName", "person_name"),
        "group": pick_loose(raw, "group_name", "groupName", "license_plate_group_name"),
        "image_url": pick_loose(
            raw, "image", "image_url", "imageUrl", "detected_image_url", "thumbnail"
        ),
        "enabled": to_bool(pick_loose(raw, "enable", "enabled", "active"), default=True),
        "created_at": pick_loose(raw, "created_at", "createdAt"),
        "raw": dict(raw),
    }


def normalize_event(
    raw: Mapping[str, Any], *, source: str, received_at: str | None = None
) -> dict[str, Any]:
    """Normalize realtime, webhook and tracking records into one event card."""
    payload = dict(raw)
    if not _looks_like_event(payload):
        nested = unwrap(raw)
        if isinstance(nested, Mapping):
            payload = dict(nested)
    event_id = pick_loose(payload, "event_id", "eventId", "id", "tracking_id")
    kind_value = pick_loose(
        payload,
        "data_type",
        "dataType",
        "event_type",
        "eventType",
        "type",
        "event",
        "action_type",
    )
    person_name = pick_loose(payload, "person_name", "personName", "name")
    person_title = pick_loose(payload, "person_title", "personTitle", "title", "type_name")
    device_name = pick_loose(payload, "device_name", "deviceName", "camera_name")
    numeric_kind = isinstance(kind_value, (int, float)) or str(kind_value or "").lstrip(
        "-"
    ).isdigit()
    event_type_code: int | None = None
    if numeric_kind:
        event_type_code = int(float(kind_value))
    if pick_loose(payload, "license_plate", "plate_number"):
        kind = "plate"
    elif event_type_code is not None:
        kind = EVENT_KIND_BY_CODE.get(event_type_code, "checkin")
    elif kind_value in {None, ""}:
        kind = "checkin"
    else:
        kind = str(kind_value)
    image_url = pick_loose(
        payload,
        "detected_image_url",
        "detectedImageUrl",
        "image_checkin",
        "imageCheckin",
        "image_url",
        "imageUrl",
        "snapshot_url",
        "snapshotUrl",
        "thumbnail",
        "thumb",
        "image",
        "url",
        "bkg_url",
        "avatar",
        "avatar_url",
    )
    occurred = pick_loose(
        payload,
        "date",
        "occurred_at",
        "occurredAt",
        "checkin_time",
        "checkinTime",
        "created_at",
        "createdAt",
        "time",
        "timestamp",
    )
    title = person_name or person_title or _event_title(kind)
    return {
        "id": str(event_id) if event_id is not None else "",
        "source": source,
        "kind": kind,
        "kind_name": EVENT_KIND_NAMES.get(kind, str(kind)),
        "event_type_code": event_type_code,
        "recognized": bool(
            pick_loose(payload, "person_id", "personID", "personId")
            and kind in {"employee", "visitor", "checkin", "face"}
        ),
        "title": str(title),
        "person_id": _string_id(pick_loose(payload, "person_id", "personID", "personId")),
        "person_name": person_name,
        "person_title": person_title,
        "device_id": _string_id(pick_loose(payload, "device_id", "deviceID", "deviceId")),
        "device_name": device_name,
        "place_id": _string_id(pick_loose(payload, "place_id", "placeID", "placeId")),
        "place_name": pick_loose(payload, "place_name", "placeName"),
        "image_url": image_url,
        "occurred_at": _normalize_time(occurred),
        "received_at": received_at or _utc_now(),
        "raw": dict(raw),
    }


def merge_device(base: Mapping[str, Any], *updates: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge status/settings responses into a normalized device."""
    merged = dict(base)
    merged["settings"] = dict(base.get("settings") or {})
    merged["features"] = dict(base.get("features") or {})
    merged["raw"] = dict(base.get("raw") or {})
    for update in updates:
        if not isinstance(update, Mapping):
            continue
        flat = flatten_mapping(update)
        merged["raw"].update(update)
        for key in ("setting", "settings", "config", "user_config"):
            nested = update.get(key)
            if isinstance(nested, Mapping):
                merged["settings"].update(nested)
        for key in ("features", "device_features"):
            nested = update.get(key)
            if isinstance(nested, Mapping):
                merged["features"].update(nested)
        status = pick(
            update,
            "online",
            "is_online",
            "isOnline",
            "is_active",
            "isActive",
            "connected",
            "connection_status",
            "connectionStatus",
            "status",
        )
        if status is not None:
            merged["status"] = status
            merged["online"] = to_bool(status)
        media = _extract_media(update)
        for key, value in media.items():
            if value is not None:
                merged[key] = value
        firmware = pick(flat, "firmware_version", "firmwareVersion", "firmware")
        latest = pick(flat, "firmware_latest", "latest_firmware", "latestFirmware")
        if firmware is not None:
            merged["firmware"] = firmware
        if latest is not None:
            merged["latest_firmware"] = latest
    return merged


def find_by_id(values: Iterable[Mapping[str, Any]], item_id: str) -> Mapping[str, Any] | None:
    """Find a raw or normalized object by common identifier keys."""
    wanted = str(item_id)
    for value in values:
        candidate = pick(value, "id", "device_id", "deviceId", "camera_id", "cameraId", "serial")
        if candidate is not None and str(candidate) == wanted:
            return value
    return None


def redact(value: Any) -> Any:
    """Recursively redact credentials and signed URL query strings."""
    secret_keys = {
        "password",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "authorization",
        "auth",
        "authkey",
        "auth_key",
        "license_key",
        "licensekey",
        "uuid",
        "p2p_id",
        "p2pid",
        "mqtt_pwd",
        "rtsp_pwd",
        "api_access_key",
        "webhook_secret",
    }
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, nested in value.items():
            output[str(key)] = "***" if str(key).lower() in secret_keys else redact(nested)
        return output
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def _canonical_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _looks_like_event(value: Mapping[str, Any]) -> bool:
    keys = {_canonical_key(str(key)) for key in value}
    return bool(
        keys
        & {
            "deviceid",
            "devicename",
            "personid",
            "personname",
            "placeid",
            "timestamp",
            "detectedimageurl",
            "bkgurl",
        }
    )


def _string_id(value: Any) -> str:
    return str(value) if value is not None else ""


def _normalize_time(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if abs(float(value)) > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, UTC).isoformat(timespec="seconds")
        except (OSError, OverflowError, ValueError):
            return str(value)
    return str(value)


def _event_title(kind: str) -> str:
    normalized = _canonical_key(kind)
    if normalized == "employee":
        return "Nhân viên"
    if normalized == "visitor":
        return "Khách"
    if normalized == "stranger":
        return "Phát hiện người lạ"
    if normalized == "alarm":
        return "Cảnh báo"
    if normalized in {"log", "checkin", "person", "face", "realtimecheckin"}:
        return "Người chưa xác định"
    if "human" in normalized:
        return "Phát hiện người"
    if "plate" in normalized or "vehicle" in normalized:
        return "Nhận diện biển số"
    if "device" in normalized:
        return "Trạng thái thiết bị"
    return "Sự kiện HANET"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
