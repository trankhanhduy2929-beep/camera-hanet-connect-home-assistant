"""UI configuration flow for the licensed HANET Connect integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._errors import HanetConfigurationError
from .api import (
    HanetGatewayAuthError,
    HanetGatewayClient,
    HanetGatewayConnectionError,
    HanetGatewayError,
)
from .const import (
    CONF_API_BASE,
    CONF_LICENSE_KEY,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_TLS,
    DEFAULT_API_BASE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .license import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_GRACE,
    LICENSE_STATUS_PENDING,
    HanetInstallationIdentity,
    HanetLicenseClient,
    HanetLicenseConnectionError,
    HanetLicenseResponse,
    HanetLicenseResponseError,
    HanetLicenseTokenError,
    async_get_installation_identity,
    normalize_license_server_url,
)
from .license_config import DEFAULT_LICENSE_SERVER_URL
from .license_store import HanetLicenseStore, HanetStoredLicense

_LOGGER = logging.getLogger(__name__)

_LICENSE_ERROR_MAP = {
    "activation_limit": "license_activation_limit",
    "installation_deactivated": "license_deactivated",
    "installation_rejected": "license_rejected",
    "installation_revoked": "license_revoked",
    "invalid_license": "invalid_license",
    "license_expired": "license_expired",
    "license_inactive": "license_inactive",
    "license_request_rejected": "license_rejected",
}


async def _async_store_license_response(
    hass: HomeAssistant,
    *,
    server_url: str,
    identity: HanetInstallationIdentity,
    previous: HanetStoredLicense | None,
    response: HanetLicenseResponse,
) -> HanetStoredLicense:
    record = HanetStoredLicense.from_response(
        server_url=server_url,
        installation_hash=identity.installation_hash,
        previous=previous,
        response=response,
    )
    await HanetLicenseStore(hass).async_save(record)
    return record


def _license_error_key(code: str) -> str:
    return _LICENSE_ERROR_MAP.get(code, "license_rejected")


def _resolve_server_url(record: HanetStoredLicense | None) -> str:
    candidate = str((record.server_url if record else "") or DEFAULT_LICENSE_SERVER_URL)
    return normalize_license_server_url(candidate)


async def _async_cached_license_state(
    hass: HomeAssistant,
    identity: HanetInstallationIdentity,
    record: HanetStoredLicense | None,
) -> str:
    if record is None:
        return "not_configured"
    if record.installation_hash != identity.installation_hash:
        return "installation_mismatch"
    if record.status == LICENSE_STATUS_PENDING:
        return LICENSE_STATUS_PENDING
    if not record.lease_token:
        return record.status
    try:
        client = HanetLicenseClient(hass, record.server_url, identity)
        return client.verify_lease(record.lease_token).state_at()
    except (HanetLicenseTokenError, ValueError):
        return "invalid_lease"


class HanetConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one licensed HANET Cloud and P2P account."""

    VERSION = 5

    def __init__(self) -> None:
        self._pending_license: HanetStoredLicense | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Activate this Home Assistant installation."""
        identity = await async_get_installation_identity(self.hass)
        store = HanetLicenseStore(self.hass)
        record = await store.async_load()
        cached_state = await _async_cached_license_state(self.hass, identity, record)
        if user_input is None:
            if cached_state in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
                return await self.async_step_account()
            if cached_state == LICENSE_STATUS_PENDING and record is not None:
                self._pending_license = record
                return await self.async_step_activation_pending()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                server_url = _resolve_server_url(record)
                response = await HanetLicenseClient(
                    self.hass, server_url, identity
                ).async_activate(str(user_input[CONF_LICENSE_KEY]))
                record = await _async_store_license_response(
                    self.hass,
                    server_url=server_url,
                    identity=identity,
                    previous=None,
                    response=response,
                )
            except ValueError as err:
                key = str(err)
                if key == "invalid_server_url":
                    errors["base"] = key
                else:
                    errors[CONF_LICENSE_KEY] = key
            except HanetLicenseConnectionError:
                errors["base"] = "cannot_connect_license"
            except HanetLicenseResponseError as err:
                errors["base"] = _license_error_key(err.code)
            except HanetLicenseTokenError:
                errors["base"] = "invalid_license_response"
            except Exception:
                _LOGGER.exception("Unexpected exception during HANET activation")
                errors["base"] = "unknown"
            else:
                if response.status in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
                    return await self.async_step_account()
                if response.status == LICENSE_STATUS_PENDING:
                    self._pending_license = record
                    return await self.async_step_activation_pending()
                errors["base"] = _license_error_key(response.status)

        schema = {
            vol.Required(CONF_LICENSE_KEY): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"activation_code": identity.activation_code},
        )

    async def async_step_activation_pending(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for manual approval when first-use activation is disabled."""
        record = (
            self._pending_license or await HanetLicenseStore(self.hass).async_load()
        )
        identity = await async_get_installation_identity(self.hass)
        if record is None or record.installation_hash != identity.installation_hash:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                response = await HanetLicenseClient(
                    self.hass, record.server_url, identity
                ).async_refresh(record.refresh_token)
                record = await _async_store_license_response(
                    self.hass,
                    server_url=record.server_url,
                    identity=identity,
                    previous=record,
                    response=response,
                )
            except HanetLicenseConnectionError:
                errors["base"] = "cannot_connect_license"
            except HanetLicenseResponseError as err:
                errors["base"] = _license_error_key(err.code)
            except HanetLicenseTokenError:
                errors["base"] = "invalid_license_response"
            else:
                if response.status in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
                    return await self.async_step_account()
                if response.status != LICENSE_STATUS_PENDING:
                    return await self.async_step_user()
                errors["base"] = "license_pending"
            self._pending_license = record

        return self.async_show_form(
            step_id="activation_pending",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"activation_code": record.activation_code},
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and store the HANET account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(user_input)
            if not errors:
                data = _normalized(user_input)
                await self.async_set_unique_id(data[CONF_USERNAME].casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_USERNAME], data=data)
        return self.async_show_form(
            step_id="account",
            data_schema=_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update cloud credentials and polling."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data=_normalized(user_input)
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Request fresh cloud credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save a replacement username/password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**entry.data, **user_input}
            errors = await self._validate(merged)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: str(user_input[CONF_USERNAME]).strip(),
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the HANET license options flow."""
        return HanetConnectOptionsFlow()

    async def _validate(self, data: dict[str, Any]) -> dict[str, str]:
        try:
            client = _client(self.hass, _normalized(data))
            await client.async_validate()
        except (ValueError, HanetConfigurationError):
            return {CONF_API_BASE: "invalid_url"}
        except HanetGatewayAuthError:
            return {"base": "invalid_auth"}
        except HanetGatewayConnectionError:
            return {"base": "cannot_connect"}
        except HanetGatewayError:
            return {"base": "unknown"}
        finally:
            if "client" in locals():
                await client.async_close()
        return {}


class HanetConnectOptionsFlow(config_entries.OptionsFlow):
    """Manage the activation for this Home Assistant installation."""

    def __init__(self) -> None:
        self._pending_license: HanetStoredLicense | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Open license management."""
        return await self.async_step_license()

    async def async_step_license(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Activate, replace or refresh this installation license."""
        identity = await async_get_installation_identity(self.hass)
        store = HanetLicenseStore(self.hass)
        record = await store.async_load()
        status = await _async_cached_license_state(self.hass, identity, record)
        errors: dict[str, str] = {}

        if user_input is not None:
            license_key = str(user_input.get(CONF_LICENSE_KEY, "")).strip()
            response: HanetLicenseResponse | None = None
            try:
                server_url = _resolve_server_url(record)
                client = HanetLicenseClient(self.hass, server_url, identity)
                if license_key:
                    response = await client.async_activate(license_key)
                elif record is not None and record.installation_hash == identity.installation_hash:
                    response = await client.async_refresh(record.refresh_token)
                else:
                    errors[CONF_LICENSE_KEY] = "license_key_required"

                if response is not None:
                    record = await _async_store_license_response(
                        self.hass,
                        server_url=server_url,
                        identity=identity,
                        previous=None if license_key else record,
                        response=response,
                    )
            except ValueError as err:
                key = str(err)
                if key == "invalid_server_url":
                    errors["base"] = key
                else:
                    errors[CONF_LICENSE_KEY] = key
            except HanetLicenseConnectionError:
                errors["base"] = "cannot_connect_license"
            except HanetLicenseResponseError as err:
                errors["base"] = _license_error_key(err.code)
            except HanetLicenseTokenError:
                errors["base"] = "invalid_license_response"
            except Exception:
                _LOGGER.exception("Unexpected exception while updating HANET license")
                errors["base"] = "unknown"
            else:
                if response is not None and response.status in {
                    LICENSE_STATUS_ACTIVE,
                    LICENSE_STATUS_GRACE,
                }:
                    self.config_entry.async_create_task(
                        self.hass,
                        self.hass.config_entries.async_reload(self.config_entry.entry_id),
                        "Reload HANET after license activation",
                    )
                    return self.async_create_entry(
                        title="", data=dict(self.config_entry.options)
                    )
                if response is not None and response.status == LICENSE_STATUS_PENDING:
                    self._pending_license = record
                    return await self.async_step_license_pending()
                if response is not None:
                    errors["base"] = _license_error_key(response.status)

        schema = {
            vol.Optional(CONF_LICENSE_KEY, default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        }
        return self.async_show_form(
            step_id="license",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "activation_code": identity.activation_code,
                "license_status": status,
            },
        )

    async def async_step_license_pending(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Recheck a manually approved activation."""
        record = (
            self._pending_license or await HanetLicenseStore(self.hass).async_load()
        )
        identity = await async_get_installation_identity(self.hass)
        if record is None or record.installation_hash != identity.installation_hash:
            return await self.async_step_license()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                response = await HanetLicenseClient(
                    self.hass, record.server_url, identity
                ).async_refresh(record.refresh_token)
                record = await _async_store_license_response(
                    self.hass,
                    server_url=record.server_url,
                    identity=identity,
                    previous=record,
                    response=response,
                )
            except HanetLicenseConnectionError:
                errors["base"] = "cannot_connect_license"
            except HanetLicenseResponseError as err:
                errors["base"] = _license_error_key(err.code)
            except HanetLicenseTokenError:
                errors["base"] = "invalid_license_response"
            else:
                if response.status in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE}:
                    self.config_entry.async_create_task(
                        self.hass,
                        self.hass.config_entries.async_reload(self.config_entry.entry_id),
                        "Reload HANET after license approval",
                    )
                    return self.async_create_entry(
                        title="", data=dict(self.config_entry.options)
                    )
                if response.status != LICENSE_STATUS_PENDING:
                    return await self.async_step_license()
                errors["base"] = "license_pending"
            self._pending_license = record

        return self.async_show_form(
            step_id="license_pending",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"activation_code": record.activation_code},
        )


def _client(hass: HomeAssistant, data: dict[str, Any]) -> HanetGatewayClient:
    return HanetGatewayClient(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        api_base_url=data[CONF_API_BASE],
        verify_tls=data[CONF_VERIFY_TLS],
    )


def _schema(defaults: dict[str, Any] | None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }
    )


def _normalized(data: dict[str, Any]) -> dict[str, Any]:
    return {
        **data,
        CONF_USERNAME: str(data.get(CONF_USERNAME, "")).strip(),
        CONF_PASSWORD: str(data.get(CONF_PASSWORD, "")),
        CONF_API_BASE: str(data.get(CONF_API_BASE, DEFAULT_API_BASE)).strip().rstrip("/"),
        CONF_VERIFY_TLS: bool(data.get(CONF_VERIFY_TLS, True)),
        CONF_SCAN_INTERVAL: int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    }
