"""Diagnostics support for HANET Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HanetConfigEntry

TO_REDACT = {
    "accessToken",
    "access_token",
    "apiKey",
    "api_key",
    "authKey",
    "auth_key",
    "licenseKey",
    "license_key",
    "mqttPwd",
    "mqtt_pwd",
    "p2pPassword",
    "p2p_id",
    "p2p_password",
    "p2p_pwd",
    "password",
    "peer_id",
    "refreshToken",
    "refresh_token",
    "rtspPwd",
    "rtsp_pwd",
    "secret",
    "snapshot_url",
    "streamPwd",
    "stream_url",
    "token",
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
