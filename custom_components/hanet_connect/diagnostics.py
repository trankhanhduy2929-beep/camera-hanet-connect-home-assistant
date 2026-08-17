"""Diagnostics support for HANET Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HanetConfigEntry

TO_REDACT = {
    "api_key",
    "access_token",
    "refresh_token",
    "stream_url",
    "snapshot_url",
    "peer_id",
    "p2p_id",
    "password",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HanetConfigEntry
) -> dict[str, Any]:
    """Return a redacted gateway snapshot."""
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "state": async_redact_data(
            entry.runtime_data.coordinator.data, TO_REDACT
        ),
    }
