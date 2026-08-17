"""License activation and signed entitlement verification for HANET."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import ipaddress
import json
import re
import secrets
from dataclasses import dataclass
from time import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from homeassistant.const import __version__ as HOME_ASSISTANT_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import INTEGRATION_VERSION
from .license_config import LICENSE_PUBLIC_KEY_B64

LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_DEACTIVATED = "deactivated"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_GRACE = "grace"
LICENSE_STATUS_PENDING = "pending"
LICENSE_STATUS_REJECTED = "rejected"
LICENSE_STATUS_REVOKED = "revoked"

_ACTIVATE_PATH = "/v1/licenses/activate"
_DEACTIVATE_PATH = "/v1/licenses/deactivate"
_REFRESH_PATH = "/v1/licenses/refresh"
_REQUEST_TIMEOUT_SECONDS = 15
_LICENSE_KEY_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{14,126}[A-Z0-9]$")
_INSTALLATION_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class HanetLicenseError(Exception):
    """Base class for licensing failures."""


class HanetLicenseConnectionError(HanetLicenseError):
    """Raised when the activation server cannot be reached."""


class HanetLicenseResponseError(HanetLicenseError):
    """Raised when the activation server rejects a request."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class HanetLicenseTokenError(HanetLicenseError):
    """Raised when a signed entitlement is invalid."""


@dataclass(frozen=True, slots=True)
class HanetInstallationIdentity:
    """Privacy-preserving identity for one Home Assistant instance."""

    installation_hash: str
    activation_code: str


@dataclass(frozen=True, slots=True)
class HanetLicenseEntitlement:
    """Verified entitlement fields signed by the activation server."""

    license_id: str
    installation_id: str
    installation_hash: str
    plan: str
    features: tuple[str, ...]
    issued_at: int
    expires_at: int
    grace_until: int

    def state_at(self, timestamp: int | None = None) -> str:
        """Return active, grace or expired at a Unix timestamp."""
        current = int(time()) if timestamp is None else timestamp
        if current <= self.expires_at:
            return LICENSE_STATUS_ACTIVE
        if current <= self.grace_until:
            return LICENSE_STATUS_GRACE
        return LICENSE_STATUS_EXPIRED


@dataclass(frozen=True, slots=True)
class HanetLicenseResponse:
    """Normalized response from the activation service."""

    status: str
    activation_code: str
    refresh_token: str | None
    lease_token: str | None
    entitlement: HanetLicenseEntitlement | None


def normalize_license_server_url(value: str) -> str:
    """Validate and normalize the external activation server URL."""
    normalized = value.strip().rstrip("/")
    if not normalized or len(normalized) > 2048:
        raise ValueError("invalid_server_url")

    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_server_url")

    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("invalid_server_url")

    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def normalize_license_key(value: str) -> str:
    """Normalize a customer license key without logging it."""
    normalized = value.strip().upper()
    if not _LICENSE_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("invalid_license_key")
    return normalized


async def async_get_installation_identity(
    hass: HomeAssistant,
) -> HanetInstallationIdentity:
    """Derive a non-reversible installation hash and display code."""
    raw_instance_id = await instance_id.async_get(hass)
    digest = hashlib.sha256(
        b"hanet-license-v1\0" + raw_instance_id.encode("ascii")
    ).digest()
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")[:16]
    activation_code = "HANET-" + "-".join(
        encoded[index : index + 4] for index in range(0, 16, 4)
    )
    return HanetInstallationIdentity(digest.hex(), activation_code)


class HanetLicenseClient:
    """HTTPS client for the HANET activation service."""

    def __init__(
        self,
        hass: HomeAssistant,
        server_url: str,
        identity: HanetInstallationIdentity,
    ) -> None:
        self._session = async_get_clientsession(hass)
        self.server_url = normalize_license_server_url(server_url)
        self.identity = identity
        self._public_key = _load_public_key()

    async def async_activate(self, license_key: str) -> HanetLicenseResponse:
        """Create or resume an installation activation."""
        return await self._async_request(
            _ACTIVATE_PATH,
            {
                "license_key": normalize_license_key(license_key),
                **self._installation_payload(),
            },
        )

    async def async_refresh(self, refresh_token: str) -> HanetLicenseResponse:
        """Refresh one installation and obtain a signed lease."""
        return await self._async_request(
            _REFRESH_PATH,
            {
                "refresh_token": _normalize_refresh_token(refresh_token),
                **self._installation_payload(),
            },
        )

    async def async_deactivate(self, refresh_token: str) -> None:
        """Best-effort deactivation of one installation."""
        await self._async_request(
            _DEACTIVATE_PATH,
            {
                "refresh_token": _normalize_refresh_token(refresh_token),
                **self._installation_payload(),
            },
        )

    def verify_lease(self, lease_token: str) -> HanetLicenseEntitlement:
        """Verify one compact Ed25519 entitlement token."""
        try:
            encoded_payload, encoded_signature = lease_token.split(".", 1)
            payload_bytes = _urlsafe_b64decode(encoded_payload)
            signature = _urlsafe_b64decode(encoded_signature)
            self._public_key.verify(signature, payload_bytes)
            payload = json.loads(payload_bytes)
        except (
            binascii.Error,
            InvalidSignature,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ) as err:
            raise HanetLicenseTokenError("invalid_lease_signature") from err

        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise HanetLicenseTokenError("invalid_lease_payload")

        installation_hash = payload.get("installation_hash")
        if installation_hash != self.identity.installation_hash:
            raise HanetLicenseTokenError("installation_mismatch")

        try:
            entitlement = HanetLicenseEntitlement(
                license_id=_required_string(payload, "license_id"),
                installation_id=_required_string(payload, "installation_id"),
                installation_hash=_required_string(payload, "installation_hash"),
                plan=_required_string(payload, "plan"),
                features=_string_tuple(payload.get("features")),
                issued_at=_required_int(payload, "issued_at"),
                expires_at=_required_int(payload, "expires_at"),
                grace_until=_required_int(payload, "grace_until"),
            )
        except (TypeError, ValueError) as err:
            raise HanetLicenseTokenError("invalid_lease_payload") from err

        if not (
            entitlement.issued_at <= entitlement.expires_at <= entitlement.grace_until
        ):
            raise HanetLicenseTokenError("invalid_lease_window")
        return entitlement

    def _installation_payload(self) -> dict[str, str]:
        return {
            "installation_hash": self.identity.installation_hash,
            "activation_code": self.identity.activation_code,
            "integration_version": INTEGRATION_VERSION,
            "ha_version": HOME_ASSISTANT_VERSION,
            "nonce": secrets.token_urlsafe(24),
        }

    async def _async_request(
        self, path: str, payload: dict[str, str]
    ) -> HanetLicenseResponse:
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
                response = await self._session.post(
                    f"{self.server_url}{path}",
                    json=payload,
                    headers={"Accept": "application/json"},
                )
                async with response:
                    data = await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            raise HanetLicenseConnectionError("license_server_unavailable") from err

        if not isinstance(data, dict):
            raise HanetLicenseConnectionError("invalid_license_response")
        if response.status >= 400:
            code = data.get("error")
            raise HanetLicenseResponseError(
                str(code) if isinstance(code, str) else "license_request_rejected"
            )

        status = data.get("status")
        activation_code = data.get("activation_code")
        if not isinstance(status, str) or not isinstance(activation_code, str):
            raise HanetLicenseConnectionError("invalid_license_response")

        refresh_token = data.get("refresh_token")
        lease_token = data.get("lease_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise HanetLicenseConnectionError("invalid_license_response")
        if lease_token is not None and not isinstance(lease_token, str):
            raise HanetLicenseConnectionError("invalid_license_response")

        entitlement = self.verify_lease(lease_token) if lease_token else None
        if status in {LICENSE_STATUS_ACTIVE, LICENSE_STATUS_GRACE} and not entitlement:
            raise HanetLicenseConnectionError("missing_license_lease")

        return HanetLicenseResponse(
            status=status,
            activation_code=activation_code,
            refresh_token=refresh_token,
            lease_token=lease_token,
            entitlement=entitlement,
        )


def _load_public_key() -> Ed25519PublicKey:
    try:
        public_key = serialization.load_der_public_key(
            base64.b64decode(LICENSE_PUBLIC_KEY_B64, validate=True)
        )
    except (ValueError, binascii.Error) as err:
        raise HanetLicenseTokenError("invalid_embedded_public_key") from err
    if not isinstance(public_key, Ed25519PublicKey):
        raise HanetLicenseTokenError("invalid_embedded_public_key")
    return public_key


def _normalize_refresh_token(value: str) -> str:
    normalized = value.strip()
    if not 32 <= len(normalized) <= 256 or any(char.isspace() for char in normalized):
        raise HanetLicenseResponseError("invalid_refresh_token")
    return normalized


def _urlsafe_b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(key)
    if key == "installation_hash" and not _INSTALLATION_HASH_PATTERN.fullmatch(value):
        raise ValueError(key)
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(key)
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise TypeError("features")
    return tuple(value)
