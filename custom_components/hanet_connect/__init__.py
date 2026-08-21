"""Independent HANET Cloud integration with direct native P2P media."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HanetGatewayClient, HanetGatewayError
from .const import (
    CONF_API_BASE,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_TLS,
    DEFAULT_API_BASE,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_COMMANDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import HanetCoordinator
from .license_manager import HanetLicenseManager, HanetLicenseUnavailableError

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_ENDPOINT = "endpoint"
ATTR_PAYLOAD = "payload"
ATTR_COMMAND = "command"
ATTR_OPTIONS = "options"
ATTR_SETTING = "setting"
ATTR_VALUE = "value"

SERVICE_CALL_ENDPOINT = "call_endpoint"
SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_SETTING = "set_setting"
SERVICE_REFRESH = "refresh"
SERVICE_HISTORY = "history"
SERVICE_FACEID_CREATE = "faceid_create"
SERVICE_FACEID_UPDATE = "faceid_update"
SERVICE_FACEID_DELETE = "faceid_delete"
SERVICE_FACEID_BULK_CREATE = "faceid_bulk_create"


@dataclass(slots=True)
class HanetRuntimeData:
    """Non-persistent objects owned by one config entry."""

    client: HanetGatewayClient
    coordinator: HanetCoordinator
    license_manager: HanetLicenseManager


HanetConfigEntry = ConfigEntry[HanetRuntimeData]
_LICENSE_NOTIFICATION_ID = "hanet_connect_license_activation"
ENTRY_FIELD = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
CALL_ENDPOINT_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Optional(ATTR_PAYLOAD, default={}): dict,
    }
)
SEND_COMMAND_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_COMMAND): vol.In(DEVICE_COMMANDS),
        vol.Optional(ATTR_OPTIONS, default={}): dict,
    }
)
SET_SETTING_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_SETTING): cv.string,
        vol.Required(ATTR_VALUE): object,
    }
)
REFRESH_SCHEMA = vol.Schema(
    {**ENTRY_FIELD, vol.Optional("include_settings", default=False): cv.boolean}
)
HISTORY_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("day"): cv.date,
    }
)
FACEID_CREATE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("name"): cv.string,
        vol.Required("place_id"): cv.string,
        vol.Required("image_path"): cv.string,
        vol.Optional("person_type", default=0): vol.All(vol.Coerce(int), vol.In((0, 1))),
        vol.Optional("alias_id", default=""): cv.string,
        vol.Optional("department_id", default=""): cv.string,
    }
)
FACEID_UPDATE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("person_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("place_id"): cv.string,
        vol.Optional("image_path"): cv.string,
        vol.Optional("person_type"): vol.All(vol.Coerce(int), vol.In((0, 1))),
        vol.Optional("alias_id"): cv.string,
        vol.Optional("department_id"): cv.string,
    }
)
FACEID_DELETE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("person_id"): cv.string,
        vol.Optional("place_id"): cv.string,
    }
)
FACEID_BULK_CREATE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("place_id"): cv.string,
        vol.Required("image_paths"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("person_type", default=0): vol.All(vol.Coerce(int), vol.In((0, 1))),
        vol.Optional("department_id", default=""): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration actions independently of loaded entries."""

    async def call_endpoint(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        try:
            result = await runtime.client.async_call_endpoint(
                call.data[ATTR_ENDPOINT], call.data[ATTR_PAYLOAD]
            )
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def send_command(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        try:
            result = await runtime.client.async_send_command(
                call.data[ATTR_DEVICE_ID],
                call.data[ATTR_COMMAND],
                call.data[ATTR_OPTIONS],
            )
            await runtime.coordinator.async_request_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def set_setting(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        try:
            result = await runtime.client.async_set_setting(
                call.data[ATTR_DEVICE_ID],
                call.data[ATTR_SETTING],
                call.data[ATTR_VALUE],
            )
            await runtime.coordinator.async_request_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def refresh(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        try:
            result = await runtime.client.async_refresh(
                settings=call.data["include_settings"]
            )
            await runtime.coordinator.async_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def history(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        try:
            rows = await runtime.client.async_recordings(
                call.data["day"].isoformat()
            )
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        device_id = str(call.data[ATTR_DEVICE_ID])
        return {
            "device_id": device_id,
            "day": call.data["day"].isoformat(),
            "recordings": [
                row
                for row in rows
                if str(row.get("device_id") or "") == device_id
            ],
        }

    async def faceid_create(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        path = _allowed_image_path(hass, call.data["image_path"])
        image = await hass.async_add_executor_job(path.read_bytes)
        fields = _face_fields(call.data)
        try:
            result = await runtime.client.async_upload_face(
                fields=fields,
                image=image,
                filename=path.name,
            )
            runtime.coordinator._metadata_refreshed_at = 0
            await runtime.coordinator.async_request_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def faceid_update(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        fields = {
            "person_id": call.data["person_id"],
            **_face_fields(call.data),
        }
        try:
            if image_path := call.data.get("image_path"):
                path = _allowed_image_path(hass, image_path)
                image = await hass.async_add_executor_job(path.read_bytes)
                result = await runtime.client.async_upload_face(
                    fields=fields,
                    image=image,
                    filename=path.name,
                    update=True,
                )
            else:
                result = await runtime.client.async_call_endpoint(
                    "person_update",
                    fields,
                )
            runtime.coordinator._metadata_refreshed_at = 0
            await runtime.coordinator.async_request_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def faceid_delete(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        payload = {
            key: call.data[key]
            for key in ("person_id", "place_id")
            if call.data.get(key)
        }
        try:
            result = await runtime.client.async_call_endpoint(
                "person_delete",
                payload,
            )
            runtime.coordinator._metadata_refreshed_at = 0
            await runtime.coordinator.async_request_refresh()
        except HanetGatewayError as err:
            raise ServiceValidationError(str(err)) from err
        return {"result": result}

    async def faceid_bulk_create(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime_for_call(hass, call)
        results: list[dict[str, Any]] = []
        common_fields = _face_fields(call.data)
        for image_path in call.data["image_paths"]:
            path = _allowed_image_path(hass, image_path)
            image = await hass.async_add_executor_job(path.read_bytes)
            fields = {
                **common_fields,
                "name": path.stem,
                "person_name": path.stem,
            }
            try:
                result = await runtime.client.async_upload_face(
                    fields=fields,
                    image=image,
                    filename=path.name,
                )
                results.append(
                    {"path": str(path), "ok": True, "result": result}
                )
            except HanetGatewayError as err:
                results.append(
                    {"path": str(path), "ok": False, "error": str(err)}
                )
        runtime.coordinator._metadata_refreshed_at = 0
        await runtime.coordinator.async_request_refresh()
        return {
            "created": sum(bool(item["ok"]) for item in results),
            "failed": sum(not item["ok"] for item in results),
            "results": results,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALL_ENDPOINT,
        call_endpoint,
        schema=CALL_ENDPOINT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        send_command,
        schema=SEND_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SETTING,
        set_setting,
        schema=SET_SETTING_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        refresh,
        schema=REFRESH_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_HISTORY,
        history,
        schema=HISTORY_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FACEID_CREATE,
        faceid_create,
        schema=FACEID_CREATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FACEID_UPDATE,
        faceid_update,
        schema=FACEID_UPDATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FACEID_DELETE,
        faceid_delete,
        schema=FACEID_DELETE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FACEID_BULK_CREATE,
        faceid_bulk_create,
        schema=FACEID_BULK_CREATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: HanetConfigEntry
) -> bool:
    """Migrate from the retired add-on media proxy to direct P2P."""
    if entry.version > 5:
        return False
    data = dict(entry.data)
    if entry.version < 2:
        data = {
            **data,
            CONF_API_BASE: entry.data.get(
                CONF_API_BASE, DEFAULT_API_BASE
            ),
            CONF_VERIFY_TLS: entry.data.get(CONF_VERIFY_TLS, True),
        }
    if entry.version < 4:
        data.pop("url", None)
        data.pop("api_key", None)
    if entry.version < 5:
        hass.config_entries.async_update_entry(entry, data=data, version=5)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HanetConfigEntry
) -> bool:
    """Set up one independent HANET Cloud account."""
    try:
        license_manager = await HanetLicenseManager.async_create(hass)
    except HanetLicenseUnavailableError as err:
        _show_license_notification(hass, err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="license_unavailable",
            translation_placeholders={
                "activation_code": err.activation_code,
                "license_error": err.code,
            },
        ) from err

    persistent_notification.async_dismiss(hass, _LICENSE_NOTIFICATION_ID)
    if not entry.data.get(CONF_USERNAME) or not entry.data.get(CONF_PASSWORD):
        raise ConfigEntryAuthFailed(
            "Enter the HANET username and password for this integration"
        )
    client = HanetGatewayClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        api_base_url=entry.data.get(CONF_API_BASE, DEFAULT_API_BASE),
        verify_tls=bool(entry.data.get(CONF_VERIFY_TLS, True)),
        ffmpeg_binary=get_ffmpeg_manager(hass).binary,
    )
    coordinator = HanetCoordinator(
        hass,
        entry,
        client,
        int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = HanetRuntimeData(client, coordinator, license_manager)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await client.async_close()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    license_manager.async_start(
        entry,
        lambda err: _async_handle_invalid_license(hass, entry, err),
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HanetConfigEntry
) -> bool:
    """Unload all HANET entity platforms."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unloaded:
        await entry.runtime_data.license_manager.async_stop()
        await entry.runtime_data.client.async_close()
    return unloaded


async def _async_reload_entry(
    hass: HomeAssistant, entry: HanetConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_invalid_license(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    err: HanetLicenseUnavailableError,
) -> None:
    """Reload an entry after its signed lease becomes unusable."""
    _show_license_notification(hass, err)
    await hass.config_entries.async_reload(entry.entry_id)


def _show_license_notification(
    hass: HomeAssistant, err: HanetLicenseUnavailableError
) -> None:
    """Show activation guidance without exposing the license key."""
    persistent_notification.async_create(
        hass,
        (
            "HANET Connect chưa có giấy phép hợp lệ. Mở Cài đặt > Thiết bị & "
            "dịch vụ > HANET Connect > Cấu hình để nhập server và license key. "
            f"Mã cài đặt: {err.activation_code}. Trạng thái: {err.code}."
        ),
        title="Kích hoạt HANET Connect",
        notification_id=_LICENSE_NOTIFICATION_ID,
    )


def _runtime_for_call(
    hass: HomeAssistant, call: ServiceCall
) -> HanetRuntimeData:
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError("HANET config entry was not found")
    else:
        loaded = [item for item in entries if item.state is ConfigEntryState.LOADED]
        if len(loaded) != 1:
            raise ServiceValidationError(
                "config_entry_id is required when zero or multiple HANET entries are loaded"
            )
        entry = loaded[0]
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("HANET config entry is not loaded")
    typed_entry = cast(HanetConfigEntry, entry)
    runtime = typed_entry.runtime_data
    if not isinstance(runtime, HanetRuntimeData):
        raise ServiceValidationError("HANET config entry has no active runtime")
    return runtime


def _allowed_image_path(hass: HomeAssistant, value: str) -> Path:
    path = Path(value).expanduser()
    if not hass.config.is_allowed_path(str(path)):
        raise ServiceValidationError(
            "image_path must be inside a Home Assistant allowlisted path"
        )
    if not path.is_file():
        raise ServiceValidationError("FaceID image does not exist or is not a file")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ServiceValidationError("FaceID image must be JPEG or PNG")
    return path


def _face_fields(data: dict[str, Any]) -> dict[str, Any]:
    name = data.get("name")
    return {
        key: value
        for key, value in {
            "place_id": data.get("place_id"),
            "name": name,
            "person_name": name,
            "type": data.get("person_type"),
            "alias_id": data.get("alias_id"),
            "department_id": data.get("department_id"),
        }.items()
        if value not in (None, "")
    }
