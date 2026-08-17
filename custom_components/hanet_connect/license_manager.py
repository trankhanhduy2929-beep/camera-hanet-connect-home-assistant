"""Runtime enforcement for HANET activation leases."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .license import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_GRACE,
    LICENSE_STATUS_PENDING,
    HanetInstallationIdentity,
    HanetLicenseClient,
    HanetLicenseConnectionError,
    HanetLicenseEntitlement,
    HanetLicenseError,
    HanetLicenseResponseError,
    HanetLicenseTokenError,
    async_get_installation_identity,
)
from .license_store import HanetLicenseStore, HanetStoredLicense

_LOGGER = logging.getLogger(__name__)

LICENSE_REFRESH_INTERVAL_SECONDS = 12 * 60 * 60
LICENSE_REFRESH_JITTER_SECONDS = 10 * 60


class HanetLicenseUnavailableError(HanetLicenseError):
    """Raised when no currently usable activation exists."""

    def __init__(self, code: str, activation_code: str) -> None:
        super().__init__(code)
        self.code = code
        self.activation_code = activation_code


class HanetLicenseManager:
    """Validate cached licenses and refresh them in the background."""

    def __init__(
        self,
        hass: HomeAssistant,
        identity: HanetInstallationIdentity,
        store: HanetLicenseStore,
        record: HanetStoredLicense,
    ) -> None:
        self.hass = hass
        self.identity = identity
        self.store = store
        self.record = record
        self.entitlement: HanetLicenseEntitlement | None = None
        self.state = record.status
        self._task: asyncio.Task[None] | None = None

    @classmethod
    async def async_create(cls, hass: HomeAssistant) -> HanetLicenseManager:
        """Load and validate the activation for this HA instance."""
        identity = await async_get_installation_identity(hass)
        store = HanetLicenseStore(hass)
        record = await store.async_load()
        if record is None:
            raise HanetLicenseUnavailableError(
                "license_not_configured", identity.activation_code
            )
        if record.installation_hash != identity.installation_hash:
            raise HanetLicenseUnavailableError(
                "license_installation_mismatch", identity.activation_code
            )

        manager = cls(hass, identity, store, record)
        await manager.async_validate()
        return manager

    async def async_validate(self) -> None:
        """Refresh from the server, falling back to a signed cached lease."""
        try:
            client = HanetLicenseClient(
                self.hass,
                self.record.server_url,
                self.identity,
            )
            response = await client.async_refresh(self.record.refresh_token)
        except HanetLicenseConnectionError:
            self._validate_cached_lease(client)
            return
        except (HanetLicenseTokenError, ValueError) as err:
            raise HanetLicenseUnavailableError(
                "license_invalid_configuration", self.identity.activation_code
            ) from err
        except HanetLicenseResponseError as err:
            raise HanetLicenseUnavailableError(
                err.code, self.identity.activation_code
            ) from err

        if response.status == LICENSE_STATUS_PENDING:
            refreshed = HanetStoredLicense.from_response(
                server_url=self.record.server_url,
                installation_hash=self.identity.installation_hash,
                previous=self.record,
                response=response,
            )
            await self.store.async_save(refreshed)
            self.record = refreshed
            raise HanetLicenseUnavailableError(
                "license_pending", self.identity.activation_code
            )

        if response.status not in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
            raise HanetLicenseUnavailableError(
                f"license_{response.status}", self.identity.activation_code
            )

        refreshed = HanetStoredLicense.from_response(
            server_url=self.record.server_url,
            installation_hash=self.identity.installation_hash,
            previous=self.record,
            response=response,
        )
        await self.store.async_save(refreshed)
        self.record = refreshed
        self.entitlement = response.entitlement
        self.state = (
            response.entitlement.state_at() if response.entitlement else response.status
        )

    def async_start(
        self,
        entry: ConfigEntry,
        on_invalid: Callable[[HanetLicenseUnavailableError], Awaitable[None]],
    ) -> None:
        """Start periodic refresh for one loaded config entry."""
        if self._task is not None:
            return
        self._task = entry.async_create_background_task(
            self.hass,
            self._async_refresh_loop(on_invalid),
            "HANET license refresh",
        )

    async def async_stop(self) -> None:
        """Stop periodic license refresh."""
        task = self._task
        self._task = None
        if task is None or task is asyncio.current_task():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _validate_cached_lease(self, client: HanetLicenseClient) -> None:
        lease_token = self.record.lease_token
        if not lease_token:
            raise HanetLicenseUnavailableError(
                "license_server_unavailable", self.identity.activation_code
            )
        try:
            entitlement = client.verify_lease(lease_token)
        except HanetLicenseTokenError as err:
            raise HanetLicenseUnavailableError(
                "license_invalid_lease", self.identity.activation_code
            ) from err
        state = entitlement.state_at()
        if state not in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
            raise HanetLicenseUnavailableError(
                "license_offline_grace_expired", self.identity.activation_code
            )
        self.entitlement = entitlement
        self.state = state

    async def _async_refresh_loop(
        self,
        on_invalid: Callable[[HanetLicenseUnavailableError], Awaitable[None]],
    ) -> None:
        while True:
            await asyncio.sleep(
                LICENSE_REFRESH_INTERVAL_SECONDS
                + random.randint(0, LICENSE_REFRESH_JITTER_SECONDS)
            )
            try:
                await self.async_validate()
            except HanetLicenseUnavailableError as err:
                _LOGGER.warning("HANET license became unavailable: %s", err.code)
                await on_invalid(err)
                return
