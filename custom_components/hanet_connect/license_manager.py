"""Runtime enforcement for HANET activation leases."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import Awaitable, Callable
from time import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .license import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_EXPIRED,
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
from .license_config import DEFAULT_LICENSE_SERVER_URL
from .license_store import HanetLicenseStore, HanetStoredLicense

_LOGGER = logging.getLogger(__name__)

LICENSE_REFRESH_INTERVAL_SECONDS = 12 * 60 * 60
LICENSE_REFRESH_JITTER_SECONDS = 10 * 60
LICENSE_RETRY_INTERVAL_SECONDS = 60
LICENSE_RETRY_MAX_INTERVAL_SECONDS = 15 * 60


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
        self._retry = False
        self._retry_attempts = 0

    @classmethod
    async def async_create(cls, hass: HomeAssistant) -> HanetLicenseManager:
        """Load and validate the activation for this HA instance."""
        identity = None
        try:
            identity = await async_get_installation_identity(hass)
            store = HanetLicenseStore(hass)
            record = await store.async_load()
        except Exception:
            raise HanetLicenseUnavailableError(
                "license_storage_unavailable", identity.activation_code if identity else ""
            ) from None
        if record is None:
            raise HanetLicenseUnavailableError(
                "license_not_configured", identity.activation_code
            )
        if record.installation_hash != identity.installation_hash:
            raise HanetLicenseUnavailableError(
                "license_installation_mismatch", identity.activation_code
            )
        if (
            record.installation_id != identity.installation_id
            or record.installation_public_key != identity.public_key
        ):
            raise HanetLicenseUnavailableError(
                "license_installation_mismatch", identity.activation_code
            )

        manager = cls(hass, identity, store, record)
        await manager.async_validate(allow_cached=True)
        return manager

    async def async_validate(self, *, allow_cached: bool = False) -> None:
        """Refresh from the server, falling back to a signed cached lease."""
        self._retry = False
        try:
            client = HanetLicenseClient(
                self.hass,
                DEFAULT_LICENSE_SERVER_URL,
                self.identity,
            )
        except (HanetLicenseTokenError, ValueError) as err:
            raise HanetLicenseUnavailableError(
                "license_invalid_configuration", self.identity.activation_code
            ) from err

        if allow_cached:
            try:
                self._validate_cached_lease(client)
            except HanetLicenseUnavailableError:
                pass
            else:
                entitlement = self.entitlement
                assert entitlement is not None
                if (
                    self.state == LICENSE_STATUS_ACTIVE
                    and entitlement.expires_at - time()
                    >= LICENSE_REFRESH_INTERVAL_SECONDS
                ):
                    return

        try:
            response = await client.async_refresh(self.record.refresh_token)
        except HanetLicenseConnectionError:
            self._retry = True
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
        except Exception:
            _LOGGER.warning("HANET license refresh failed; validating signed cache")
            self._retry = True
            self._validate_cached_lease(client)
            return

        if response.status == LICENSE_STATUS_PENDING:
            self.entitlement = None
            self.state = LICENSE_STATUS_PENDING
            try:
                refreshed = HanetStoredLicense.from_response(
                    server_url=DEFAULT_LICENSE_SERVER_URL,
                    identity=self.identity,
                    previous=self.record,
                    response=response,
                )
                await self.store.async_save(refreshed)
                self.record = refreshed
            except Exception:
                _LOGGER.warning("HANET pending license cache could not be saved")
            raise HanetLicenseUnavailableError(
                "license_pending", self.identity.activation_code
            )
        if response.status not in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
            raise HanetLicenseUnavailableError(
                f"license_{response.status}", self.identity.activation_code
            )

        if not response.lease_token:
            raise HanetLicenseUnavailableError(
                "license_invalid_lease", self.identity.activation_code
            )
        try:
            refreshed = HanetStoredLicense.from_response(
                server_url=DEFAULT_LICENSE_SERVER_URL,
                identity=self.identity,
                previous=self.record,
                response=response,
            )
        except (TypeError, ValueError) as err:
            raise HanetLicenseUnavailableError(
                "license_invalid_configuration", self.identity.activation_code
            ) from err
        self._validate_cached_lease(client, refreshed)
        self.record = refreshed
        try:
            async with asyncio.timeout(self._remaining_lease_seconds()):
                await self.store.async_save(refreshed)
        except Exception:
            _LOGGER.warning("HANET license cache could not be saved; retrying")
            self._retry = True
        self._remaining_lease_seconds()

    def async_start(
        self,
        entry: ConfigEntry,
        on_invalid: Callable[[HanetLicenseUnavailableError], Awaitable[None]],
    ) -> None:
        """Start periodic refresh for one loaded config entry."""
        if self._task is not None and not self._task.done():
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

    def _validate_cached_lease(
        self, client: HanetLicenseClient, record: HanetStoredLicense | None = None
    ) -> None:
        lease_token = (record or self.record).lease_token
        if not lease_token:
            raise HanetLicenseUnavailableError(
                "license_server_unavailable", self.identity.activation_code
            )
        try:
            entitlement = client.verify_lease(lease_token)
        except (HanetLicenseTokenError, ValueError, TypeError) as err:
            raise HanetLicenseUnavailableError(
                "license_invalid_lease", self.identity.activation_code
            ) from err
        state = entitlement.state_at()
        if (
            state not in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}
            or entitlement.grace_until <= time()
        ):
            raise HanetLicenseUnavailableError(
                "license_offline_grace_expired", self.identity.activation_code
            )
        self.entitlement = entitlement
        self.state = state

    def _remaining_lease_seconds(self) -> float:
        if self.entitlement is None:
            raise HanetLicenseUnavailableError(
                "license_invalid_lease", self.identity.activation_code
            )
        remaining = self.entitlement.grace_until - time()
        if remaining <= 0:
            raise HanetLicenseUnavailableError(
                "license_offline_grace_expired", self.identity.activation_code
            )
        self.state = self.entitlement.state_at()
        return remaining

    def _next_delay(self) -> float:
        if self._retry:
            delay = min(
                LICENSE_RETRY_INTERVAL_SECONDS * 2**self._retry_attempts,
                LICENSE_RETRY_MAX_INTERVAL_SECONDS,
            )
            self._retry_attempts += 1
        else:
            self._retry_attempts = 0
            delay = LICENSE_REFRESH_INTERVAL_SECONDS + random.randint(
                0, LICENSE_REFRESH_JITTER_SECONDS
            )
        delay = min(delay, self._remaining_lease_seconds())
        if self.entitlement is not None:
            active_remaining = self.entitlement.expires_at - time()
            if active_remaining > 0:
                delay = min(delay, active_remaining)
        return delay

    async def _async_refresh_loop(
        self,
        on_invalid: Callable[[HanetLicenseUnavailableError], Awaitable[None]],
    ) -> None:
        try:
            while True:
                delay = self._next_delay()
                await asyncio.sleep(delay)
                remaining = self._remaining_lease_seconds()
                try:
                    async with asyncio.timeout(remaining):
                        await self.async_validate()
                except HanetLicenseUnavailableError:
                    raise
                except Exception:
                    _LOGGER.warning(
                        "HANET license refresh interrupted; retrying within signed lease"
                    )
                    self._retry = True
                    self._remaining_lease_seconds()
        except HanetLicenseUnavailableError as err:
            self.entitlement = None
            self.state = LICENSE_STATUS_EXPIRED
            _LOGGER.warning("HANET license became unavailable: %s", err.code)
            self.hass.async_create_task(on_invalid(err), "HANET license invalidation")
        finally:
            if self._task is asyncio.current_task():
                self._task = None
