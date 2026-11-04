"""FaceID request contracts verified against HANET Connect 4.1.21."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PERSON_ID_KEYS = ("person_id", "personID", "personId")
PLACE_KEYS = ("place_id", "placeId", "placeID")
DEPARTMENT_KEYS = ("department_id", "departmentId", "departmentID")
PREVIOUS_DEPARTMENT_KEYS = (
    "previous_department_id",
    "previousDepartmentId",
    "previousDepartmentID",
)


def _field(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _has(source: Mapping[str, Any], *keys: str) -> bool:
    return any(key in source for key in keys)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _cloud_id(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate:
        return value
    try:
        return int(candidate, 10)
    except ValueError:
        return value


def _enum(value: Any, label: str) -> int:
    try:
        converted = int(str(value).strip(), 10)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{label} không hợp lệ") from err
    if converted not in (0, 1):
        raise ValueError(f"{label} không hợp lệ")
    return converted


def person_update_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Build the JSON body accepted by /business/person/update.

    The mobile app sends ``person_id`` as a string, requires a name, omits
    ``place_id`` and sends profile fields verbatim so an empty value clears
    the old value.
    """
    person_id = _text(_field(data, *PERSON_ID_KEYS))
    name = _text(_field(data, "name", "person_name", "personName"))
    if not person_id:
        raise ValueError("FaceID cần có mã nhận diện")
    if not name:
        raise ValueError("Cần tên để cập nhật FaceID")
    payload: dict[str, Any] = {"person_id": person_id, "name": name}
    person_type = _field(data, "type", "person_type", "personType")
    if person_type not in (None, ""):
        payload["type"] = _enum(person_type, "Loại FaceID")
    sex = _field(data, "sex", "gender")
    if sex not in (None, ""):
        payload["sex"] = _enum(sex, "Giới tính FaceID")
    for target, keys in (
        ("title", ("title",)),
        ("phone", ("phone",)),
        ("dob", ("dob", "date_of_birth", "dateOfBirth")),
        ("email", ("email",)),
        ("alias_id", ("alias_id", "aliasId", "aliasID")),
    ):
        if _has(data, *keys):
            payload[target] = _text(_field(data, *keys))
    if _has(data, *DEPARTMENT_KEYS):
        department_id = _text(_field(data, *DEPARTMENT_KEYS))
        if department_id:
            payload["department_id"] = _cloud_id(department_id)
    return payload


def person_department_ids(data: Mapping[str, Any]) -> tuple[str, str]:
    """Return the requested and previous department IDs from a payload."""
    requested = (
        _text(_field(data, *DEPARTMENT_KEYS))
        if _has(data, *DEPARTMENT_KEYS)
        else ""
    )
    previous = _text(_field(data, *PREVIOUS_DEPARTMENT_KEYS))
    return requested, previous

def person_place_id(data: Mapping[str, Any]) -> str:
    """Return the place ID used for multipart and membership calls."""
    return _text(_field(data, *PLACE_KEYS))

def person_face_update_fields(data: Mapping[str, Any]) -> dict[str, str]:
    """Keep only the multipart fields accepted by update-by-face-image."""
    fields: dict[str, str] = {}
    person_id = _text(_field(data, *PERSON_ID_KEYS))
    place_id = _text(_field(data, *PLACE_KEYS))
    if person_id:
        fields["person_id"] = person_id
    if place_id:
        fields["place_id"] = place_id
    return fields
