"""Group HANET events into user-facing recognition categories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

GROUP_LABELS = {
    "alarm": "Báo động",
    "motion": "Chuyển động",
    "stranger": "Người lạ",
    "known": "Người quen",
    "employee": "Người nhà",
    "visitor": "Khách",
}

_MOTION_KINDS = {"human", "person", "face", "checkin", "motion"}


def _kind(event: Mapping[str, Any]) -> str:
    return str(event.get("kind") or "").strip().casefold().replace("-", "_")


def group_for_event(event: Mapping[str, Any]) -> str | None:
    """Return the group that best describes one event."""
    kind = _kind(event)
    if kind in {"employee", "visitor", "stranger", "alarm"}:
        return kind
    if event.get("person_id"):
        return "known"
    if kind in _MOTION_KINDS:
        return "motion"
    return None


def group_matches(group: str, event: Mapping[str, Any]) -> bool:
    """Return whether an event belongs to a sensor group."""
    kind = _kind(event)
    if group == "known":
        return kind == "visitor" or (
            bool(event.get("person_id")) and kind != "employee"
        )
    if group == "motion":
        return kind in _MOTION_KINDS and not event.get("person_id")
    return group == kind


def event_attributes(
    event: Mapping[str, Any], group: str | None = None
) -> dict[str, Any]:
    """Expose picture, time and category details for one event."""
    if not event:
        return {}
    event_group = group_for_event(event)
    active_group = group or event_group
    return {
        key: value
        for key, value in {
            "group": active_group,
            "group_name": GROUP_LABELS.get(str(active_group), ""),
            "event_group": event_group,
            "event_group_name": GROUP_LABELS.get(str(event_group), ""),
            "person_name": event.get("person_name"),
            "event_type": event.get("kind"),
            "event_type_name": event.get("kind_name") or event.get("kind"),
            "occurred_at": event.get("occurred_at"),
            "image_url": event.get("image_url"),
            "event_id": event.get("id"),
        }.items()
        if value not in (None, "")
    }
