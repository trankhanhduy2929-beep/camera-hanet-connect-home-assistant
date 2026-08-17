"""Persistent storage for HANET activation leases."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from time import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .license import HanetLicenseResponse

_STORAGE_KEY = f"{DOMAIN}.license"
_STORAGE_VERSION = 1


@dataclass(frozen=True, slots=True)
class HanetStoredLicense:
    """Activation data persisted outside config entries and diagnostics."""

    server_url: str
    installation_hash: str
    activation_code: str
    refresh_token: str
    status: str
    lease_token: str | None
    license_id: str | None
    updated_at: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HanetStoredLicense | None:
        """Parse stored data, returning None for incomplete records."""
        required = (
            "server_url",
            "installation_hash",
            "activation_code",
            "refresh_token",
            "status",
        )
        if any(not isinstance(data.get(key), str) or not data[key] for key in required):
            return None
        lease_token = data.get("lease_token")
        license_id = data.get("license_id")
        updated_at = data.get("updated_at", 0)
        if lease_token is not None and not isinstance(lease_token, str):
            return None
        if license_id is not None and not isinstance(license_id, str):
            return None
        if isinstance(updated_at, bool) or not isinstance(updated_at, int):
            return None
        return cls(
            server_url=data["server_url"],
            installation_hash=data["installation_hash"],
            activation_code=data["activation_code"],
            refresh_token=data["refresh_token"],
            status=data["status"],
            lease_token=lease_token,
            license_id=license_id,
            updated_at=updated_at,
        )

    @classmethod
    def from_response(
        cls,
        *,
        server_url: str,
        installation_hash: str,
        previous: HanetStoredLicense | None,
        response: HanetLicenseResponse,
    ) -> HanetStoredLicense:
        """Create a persistent record from an activation response."""
        refresh_token = response.refresh_token or (
            previous.refresh_token if previous else None
        )
        if not refresh_token:
            raise ValueError("missing_refresh_token")
        lease_token = response.lease_token
        if lease_token is None and previous is not None:
            lease_token = previous.lease_token
        license_id = (
            response.entitlement.license_id
            if response.entitlement
            else previous.license_id
            if previous
            else None
        )
        return cls(
            server_url=server_url,
            installation_hash=installation_hash,
            activation_code=response.activation_code,
            refresh_token=refresh_token,
            status=response.status,
            lease_token=lease_token,
            license_id=license_id,
            updated_at=int(time()),
        )


class HanetLicenseStore:
    """Read and write the one installation license for this HA instance."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            _STORAGE_VERSION,
            _STORAGE_KEY,
            private=True,
        )
        self._lock = asyncio.Lock()

    async def async_load(self) -> HanetStoredLicense | None:
        """Load the current activation record."""
        async with self._lock:
            data = await self._store.async_load()
        if not isinstance(data, dict):
            return None
        return HanetStoredLicense.from_dict(data)

    async def async_save(self, record: HanetStoredLicense) -> None:
        """Persist an activation record."""
        async with self._lock:
            await self._store.async_save(asdict(record))

    async def async_clear(self) -> None:
        """Remove the local activation cache."""
        async with self._lock:
            await self._store.async_remove()
