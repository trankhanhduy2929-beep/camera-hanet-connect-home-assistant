"""License activation and signed portal verification for HANET Connect."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import ipaddress
import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import aiohttp
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, INTEGRATION_VERSION
from .license_config import LICENSE_PUBLIC_KEY_B64

LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_DEACTIVATED = "deactivated"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_GRACE = "grace"
LICENSE_STATUS_PENDING = "pending"
LICENSE_STATUS_REJECTED = "rejected"
LICENSE_STATUS_REVOKED = "revoked"

_VERIFY_PATH = "/api/licenses/verify"
_CLIENT_TYPE = "custom_component"
_REQUEST_TIMEOUT_SECONDS = 20
_LICENSE_KEY_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{10,100}[A-Z0-9]$")
_INSTALLATION_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SIGNATURE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{80,128}$")
_SERVER_CLOCK_SKEW_SECONDS = 10 * 60
_LEASE_ACTIVE_SECONDS = 24 * 60 * 60
_LEASE_GRACE_SECONDS = 72 * 60 * 60
_SIGNATURE_VERSION = 1
_SIGNATURE_ALGORITHM = "Ed25519"
_STORED_KEY_PREFIX = "portal-v1"
_IDENTITY_STORAGE_KEY = f"{DOMAIN}.license_identity"
_IDENTITY_STORAGE_VERSION = 1
_IDENTITY_LOCK = asyncio.Lock()


class HanetLicenseError(Exception):
    """Base class for licensing failures."""


class HanetLicenseConnectionError(HanetLicenseError):
    """Raised when the portal cannot be reached."""


class HanetLicenseResponseError(HanetLicenseError):
    """Raised when the portal rejects a request."""

    def __init__(self, code: str, *, authoritative: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.authoritative = authoritative


class HanetLicenseTokenError(HanetLicenseError):
    """Raised when a signed entitlement is invalid."""


@dataclass(frozen=True, slots=True)
class HanetInstallationIdentity:
    """Stable proof-of-possession identity for one Home Assistant instance."""

    installation_hash: str
    activation_code: str
    installation_id: str = ""
    public_key: str = ""
    private_key_der: str = ""


@dataclass(frozen=True, slots=True)
class HanetLicenseEntitlement:
    """Verified entitlement fields returned by the portal."""

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
    """Normalized response from the Vercel license portal."""

    status: str
    activation_code: str
    refresh_token: str | None
    lease_token: str | None
    entitlement: HanetLicenseEntitlement | None
    verification: dict[str, Any] | None = None


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _standard_b64_decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), validate=True)


def normalize_license_server_url(value: str) -> str:
    """Validate and normalize the external license portal URL."""
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
    normalized = re.sub(r"\s+", "", value.strip().upper())
    if not _LICENSE_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("invalid_license_key")
    return normalized


async def async_get_installation_identity(
    hass: HomeAssistant,
) -> HanetInstallationIdentity:
    """Load or create a stable random Ed25519 installation identity."""
    store = Store[dict[str, str]](
        hass,
        _IDENTITY_STORAGE_VERSION,
        _IDENTITY_STORAGE_KEY,
        private=True,
    )
    async with _IDENTITY_LOCK:
        saved = await store.async_load()
        identity = _identity_from_record(saved)
        if identity is not None:
            return identity
        identity = _new_identity()
        await store.async_save(
            {
                "installation_hash": identity.installation_hash,
                "activation_code": identity.activation_code,
                "installation_id": identity.installation_id,
                "public_key": identity.public_key,
                "private_key_der": identity.private_key_der,
            }
        )
        return identity


def _new_identity() -> HanetInstallationIdentity:
    private = Ed25519PrivateKey.generate()
    raw_public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    digest = hashlib.sha256(raw_public).digest()
    public_key = _b64url_encode(raw_public)
    installation_id = f"HANET_{_b64url_encode(digest)}"
    private_der = private.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")[:16]
    activation_code = "HANET-" + "-".join(
        encoded[index : index + 4] for index in range(0, 16, 4)
    )
    return HanetInstallationIdentity(
        installation_hash=digest.hex(),
        activation_code=activation_code,
        installation_id=installation_id,
        public_key=public_key,
        private_key_der=base64.b64encode(private_der).decode("ascii"),
    )


def _identity_from_record(value: Any) -> HanetInstallationIdentity | None:
    if not isinstance(value, Mapping):
        return None
    identity = HanetInstallationIdentity(
        installation_hash=str(value.get("installation_hash") or ""),
        activation_code=str(value.get("activation_code") or ""),
        installation_id=str(value.get("installation_id") or ""),
        public_key=str(value.get("public_key") or ""),
        private_key_der=str(value.get("private_key_der") or ""),
    )
    if (
        not _INSTALLATION_HASH_PATTERN.fullmatch(identity.installation_hash)
        or not re.fullmatch(r"HANET-[A-Z2-7]{4}(?:-[A-Z2-7]{4}){3}", identity.activation_code)
        or not re.fullmatch(r"HANET_[A-Za-z0-9_-]{43}", identity.installation_id)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", identity.public_key)
        or not identity.private_key_der
    ):
        return None
    try:
        raw_public = _b64url_decode(identity.public_key)
        private = _private_key(identity)
    except (HanetLicenseTokenError, ValueError, binascii.Error):
        return None
    digest = hashlib.sha256(raw_public).digest()
    if (
        identity.installation_hash != digest.hex()
        or identity.installation_id != f"HANET_{_b64url_encode(digest)}"
        or private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        != raw_public
    ):
        return None
    return identity


def _private_key(identity: HanetInstallationIdentity) -> Ed25519PrivateKey:
    try:
        value = serialization.load_der_private_key(
            _standard_b64_decode(identity.private_key_der),
            password=None,
        )
    except (ValueError, TypeError, binascii.Error) as err:
        raise HanetLicenseTokenError("invalid_installation_private_key") from err
    if not isinstance(value, Ed25519PrivateKey):
        raise HanetLicenseTokenError("invalid_installation_private_key")
    return value


def _store_encryption_key(identity: HanetInstallationIdentity) -> bytes:
    private_der = _standard_b64_decode(identity.private_key_der)
    return hashlib.sha256(
        b"hanet-license-custom-store-v1\0" + private_der
    ).digest()


def encrypt_license_key(
    identity: HanetInstallationIdentity,
    value: str,
) -> tuple[str, str]:
    """Encrypt a license key for Home Assistant private storage."""
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_store_encryption_key(identity)).encrypt(
        nonce,
        value.encode("utf-8"),
        identity.installation_id.encode("utf-8"),
    )
    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
    )


def decrypt_license_key(
    identity: HanetInstallationIdentity,
    ciphertext: str,
    nonce: str,
) -> str:
    """Decrypt a license key from Home Assistant private storage."""
    try:
        value = AESGCM(_store_encryption_key(identity)).decrypt(
            _standard_b64_decode(nonce),
            _standard_b64_decode(ciphertext),
            identity.installation_id.encode("utf-8"),
        )
        return value.decode("utf-8")
    except (InvalidTag, ValueError, UnicodeDecodeError, binascii.Error):
        return ""


def _protect_license_key(
    identity: HanetInstallationIdentity,
    license_key: str,
) -> str:
    ciphertext, nonce = encrypt_license_key(identity, license_key)
    return f"{_STORED_KEY_PREFIX}.{nonce}.{ciphertext}"


def _stored_license_key(
    identity: HanetInstallationIdentity,
    value: str,
) -> str:
    if value.startswith(f"{_STORED_KEY_PREFIX}."):
        parts = value.split(".", 2)
        if len(parts) != 3:
            raise HanetLicenseResponseError("invalid_stored_license_key")
        decrypted = decrypt_license_key(identity, parts[2], parts[1])
        if not decrypted:
            raise HanetLicenseResponseError("invalid_stored_license_key")
        return normalize_license_key(decrypted)
    return normalize_license_key(value)


def license_portal_link(
    server_url: str,
    identity: HanetInstallationIdentity,
) -> str:
    """Return the account/installation claim link for this custom component."""
    query = urlencode(
        {
            "installation_id": identity.installation_id,
            "installation_public_key": identity.public_key,
            "addon_version": INTEGRATION_VERSION,
            "client_type": _CLIENT_TYPE,
        }
    )
    return f"{normalize_license_server_url(server_url)}/activate?{query}"


def _scalar(value: str | int | bool | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _verification_message(payload: Mapping[str, Any]) -> bytes:
    values = [
        ("signature_version", _SIGNATURE_VERSION),
        ("signature_algorithm", _SIGNATURE_ALGORITHM),
        ("valid", payload.get("valid")),
        ("request_nonce", payload.get("request_nonce")),
        ("license_key_hash", payload.get("license_key_hash")),
        ("license_id", payload.get("license_id")),
        ("plan", payload.get("plan")),
        ("installation_id", payload.get("installation_id")),
        ("starts_at", payload.get("starts_at")),
        ("expires_at", payload.get("expires_at")),
        ("server_time", payload.get("server_time")),
        ("portal_url", payload.get("portal_url")),
        ("error", payload.get("error")),
    ]
    return "\n".join(f"{key}={_scalar(value)}" for key, value in values).encode("utf-8")


def _proof_message(nonce: str, installation_id: str, key_hash: str) -> bytes:
    return "\n".join(
        [
            "hanet-license-installation-proof-v2",
            "client_type=custom_component",
            f"request_nonce={nonce}",
            f"installation_id={installation_id}",
            f"license_key_hash={key_hash}",
        ]
    ).encode("utf-8")


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_time(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class HanetLicenseClient:
    """HTTPS client for the Vercel license portal."""

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
        """Bind the custom-component slot and verify the license."""
        return await self._async_verify(license_key)

    async def async_refresh(self, license_key: str) -> HanetLicenseResponse:
        """Refresh the signed verification response."""
        return await self._async_verify(_stored_license_key(self.identity, license_key))

    async def async_deactivate(self, license_key: str) -> None:
        """Retain compatibility; removing a local key does not reset the portal slot."""
        _stored_license_key(self.identity, license_key)

    def verify_response(
        self,
        payload: Mapping[str, Any],
        *,
        expected_nonce: str | None = None,
        expected_key_hash: str | None = None,
    ) -> HanetLicenseEntitlement:
        """Verify a signed portal response and return its entitlement."""
        if (
            payload.get("signature_version") != _SIGNATURE_VERSION
            or payload.get("signature_algorithm") != _SIGNATURE_ALGORITHM
        ):
            raise HanetLicenseTokenError("unsupported_license_signature")
        request_nonce = payload.get("request_nonce")
        if not isinstance(request_nonce, str) or not _NONCE_PATTERN.fullmatch(request_nonce):
            raise HanetLicenseTokenError("invalid_license_nonce")
        if expected_nonce is not None and request_nonce != expected_nonce:
            raise HanetLicenseTokenError("license_response_binding_mismatch")
        if payload.get("installation_id") != self.identity.installation_id:
            raise HanetLicenseTokenError("license_response_binding_mismatch")
        key_hash = payload.get("license_key_hash")
        if not isinstance(key_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", key_hash):
            raise HanetLicenseTokenError("invalid_license_key_hash")
        if expected_key_hash is not None and key_hash != expected_key_hash:
            raise HanetLicenseTokenError("license_response_context_mismatch")
        if payload.get("portal_url") != self.server_url:
            raise HanetLicenseTokenError("license_response_context_mismatch")
        signature = str(payload.get("signature") or "")
        if not _SIGNATURE_PATTERN.fullmatch(signature):
            raise HanetLicenseTokenError("invalid_license_signature")
        try:
            self._public_key.verify(_b64url_decode(signature), _verification_message(payload))
        except (InvalidSignature, ValueError, TypeError, binascii.Error) as err:
            raise HanetLicenseTokenError("invalid_license_signature") from err
        server_time = _parse_time(payload.get("server_time"))
        if server_time is None or server_time > time() + _SERVER_CLOCK_SKEW_SECONDS:
            raise HanetLicenseTokenError("invalid_license_server_time")
        if not isinstance(payload.get("valid"), bool):
            raise HanetLicenseTokenError("invalid_license_entitlement")
        if payload["valid"] is False:
            code = str(payload.get("error") or "invalid_license")
            raise HanetLicenseResponseError(
                code,
                authoritative=code in {
                    "invalid_license", "license_blocked", "license_expired",
                    "activation_limit", "installation_already_claimed",
                    "installation_blocked", "installation_client_type_mismatch",
                    "installation_key_mismatch",
                },
            )

        starts_at = _parse_time(payload.get("starts_at"))
        expires_at = _parse_time(payload.get("expires_at"))
        if starts_at is None or (expires_at is not None and expires_at <= starts_at):
            raise HanetLicenseTokenError("invalid_license_entitlement")
        license_expiration = int(expires_at) if expires_at is not None else 2**63 - 1
        active_until = min(license_expiration, int(server_time) + _LEASE_ACTIVE_SECONDS)
        grace_until = min(license_expiration, int(server_time) + _LEASE_GRACE_SECONDS)
        return HanetLicenseEntitlement(
            license_id=_required_string(payload, "license_id"),
            installation_id=self.identity.installation_id,
            installation_hash=self.identity.installation_hash,
            plan=_required_string(payload, "plan"),
            features=("portal", "custom_component"),
            issued_at=int(starts_at),
            expires_at=active_until,
            grace_until=grace_until,
        )

    def verify_lease(self, lease_token: str) -> HanetLicenseEntitlement:
        """Verify a cached portal response or legacy compact lease."""
        if lease_token.lstrip().startswith("{"):
            try:
                payload = json.loads(lease_token)
            except json.JSONDecodeError as err:
                raise HanetLicenseTokenError("invalid_license_response") from err
            if not isinstance(payload, Mapping):
                raise HanetLicenseTokenError("invalid_license_response")
            try:
                return self.verify_response(payload)
            except HanetLicenseResponseError as err:
                raise HanetLicenseTokenError(err.code) from err
        try:
            encoded_payload, encoded_signature = lease_token.split(".", 1)
            payload_bytes = _b64url_decode(encoded_payload)
            signature = _b64url_decode(encoded_signature)
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
        if payload.get("installation_hash") != self.identity.installation_hash:
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
        if not entitlement.issued_at <= entitlement.expires_at <= entitlement.grace_until:
            raise HanetLicenseTokenError("invalid_lease_window")
        return entitlement

    async def _async_verify(self, license_key: str) -> HanetLicenseResponse:
        normalized_key = normalize_license_key(license_key)
        key_hash = _hash_key(normalized_key)
        nonce = _b64url_encode(secrets.token_bytes(24))
        signature = _b64url_encode(
            _private_key(self.identity).sign(
                _proof_message(nonce, self.identity.installation_id, key_hash)
            )
        )
        if not _NONCE_PATTERN.fullmatch(nonce) or not _SIGNATURE_PATTERN.fullmatch(signature):
            raise HanetLicenseTokenError("invalid_local_proof")
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
                response = await self._session.post(
                    f"{self.server_url}{_VERIFY_PATH}",
                    json={
                        "license_key": normalized_key,
                        "installation_id": self.identity.installation_id,
                        "installation_public_key": self.identity.public_key,
                        "installation_signature": signature,
                        "addon_version": INTEGRATION_VERSION,
                        "client_type": _CLIENT_TYPE,
                        "request_nonce": nonce,
                    },
                    headers={"Accept": "application/json"},
                )
                async with response:
                    data = await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            raise HanetLicenseConnectionError("license_server_unavailable") from err
        if not isinstance(data, Mapping):
            raise HanetLicenseConnectionError("invalid_license_response")
        if response.status >= 500:
            raise HanetLicenseConnectionError("license_server_unavailable")
        if response.status >= 400:
            code = data.get("error")
            raise HanetLicenseResponseError(
                str(code) if isinstance(code, str) else "license_request_rejected"
            )
        entitlement = self.verify_response(
            data,
            expected_nonce=nonce,
            expected_key_hash=key_hash,
        )
        return HanetLicenseResponse(
            status=LICENSE_STATUS_ACTIVE,
            activation_code=self.identity.activation_code,
            refresh_token=_protect_license_key(self.identity, normalized_key),
            lease_token=json.dumps(dict(data), separators=(",", ":"), sort_keys=True),
            entitlement=entitlement,
            verification=dict(data),
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


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(key)
    if key == "installation_hash" and not _INSTALLATION_HASH_PATTERN.fullmatch(value):
        raise ValueError(key)
    return value


def _required_int(payload: Mapping[str, Any], key: str) -> int:
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
