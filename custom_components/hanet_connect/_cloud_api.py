"""Async client for the HANET Connect mobile API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp

from ._catalog import ENDPOINTS
from ._errors import HanetApiError, HanetAuthError, HanetConfigurationError

_LOGGER = logging.getLogger(__name__)
_TOKEN_KEYS = {
    "access_token": ("access_token", "accessToken", "AccessToken", "token"),
    "refresh_token": ("refresh_token", "refreshToken", "RefreshToken"),
    "expires_in": ("expires_in", "expiresIn", "ExpiresIn"),
}
_NUMERIC_IDENTIFIER_KEYS = {
    "id",
    "cameraid",
    "cameraids",
    "departmentid",
    "departmentids",
    "deviceid",
    "deviceids",
    "groupid",
    "groupids",
    "licenseplateid",
    "licenseplateids",
    "personid",
    "personids",
    "placeid",
    "placeids",
    "shareid",
    "shareids",
    "subtypeid",
    "subtypeids",
    "userid",
    "userids",
}


class HanetApiClient:
    """HANET cloud session with persistent token refresh."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str = "",
        password: str = "",
        verify_tls: bool = True,
        session: aiohttp.ClientSession | None = None,
        tokens: Mapping[str, Any] | None = None,
        token_callback: Any = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise HanetConfigurationError("api_base_url must be an HTTP(S) URL")
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise HanetConfigurationError(
                "unencrypted HANET API URLs are only allowed for localhost"
            )
        self.base_url = base_url.rstrip("/") + "/"
        self.web_base_url = (
            "https://connect.hanet.ai/"
            if (parsed.hostname or "").lower().endswith("hanet.ai")
            else ""
        )
        self.username = username.strip()
        self.password = password
        self.verify_tls = verify_tls
        self._session = session
        self._owns_session = session is None
        self._token_callback = token_callback
        self._tokens: dict[str, Any] = dict(tokens or {})
        self._auth_lock = asyncio.Lock()
        self._web_authenticated = False

    @property
    def authenticated(self) -> bool:
        """Return whether an access token is available."""
        return bool(self._tokens.get("access_token"))

    @property
    def token_expiry(self) -> float | None:
        """Return the estimated token expiry epoch."""
        value = self._tokens.get("expires_at")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=35, connect=12, sock_read=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the owned HTTP session."""
        if self._session is not None and self._owns_session and not self._session.closed:
            await self._session.close()

    async def authenticate(self, *, force: bool = False) -> None:
        """Ensure a usable access token exists."""
        async with self._auth_lock:
            expiry = self.token_expiry
            if not force and self.authenticated and (expiry is None or expiry > time.time() + 60):
                return
            if self._tokens.get("refresh_token"):
                try:
                    await self._refresh_locked()
                    return
                except HanetApiError as err:
                    _LOGGER.info("HANET refresh token was rejected: status=%s", err.status)
            if not self.username or not self.password:
                raise HanetAuthError("HANET username and password are not configured", status=401)
            await self._login_locked()

    async def login(self) -> Mapping[str, Any]:
        """Authenticate with the configured username and password."""
        async with self._auth_lock:
            return await self._login_locked()

    async def list_web_places(self) -> list[Mapping[str, Any]]:
        """Discover all account places from the aggregate HANET web portal."""
        if not self.web_base_url or not self.username or not self.password:
            return []
        html = await self._web_html("/place")
        places = _rsc_objects_with_key(_next_rsc_text(html), "count_device")
        route_ids = list(
            dict.fromkeys(re.findall(r'href=[\\"\\\\]+/(\d+)/devices', html))
        )
        by_id = {
            str(place["id"]): place
            for place in places
            if place.get("id") is not None
        }
        routed = [
            by_id.get(route_id, {"id": int(route_id)})
            for route_id in route_ids
        ]
        return routed or places

    async def list_web_devices(self, place_id: str) -> list[Mapping[str, Any]]:
        """Discover devices for one place from the aggregate web inventory."""
        if not self.web_base_url or not self.username or not self.password:
            return []
        html = await self._web_html(f"/{place_id}/devices")
        candidates = _rsc_objects_with_key(_next_rsc_text(html), "device_id")
        collections = [
            value
            for candidate in candidates
            if isinstance((value := candidate.get("devices")), list)
        ]
        rows = max(collections, key=len) if collections else candidates
        return [dict(item) for item in rows if isinstance(item, Mapping)]

    async def _web_login(self) -> None:
        """Create the Auth.js session used by connect.hanet.ai inventory pages."""
        if self._web_authenticated:
            return
        if not self.username or not self.password:
            raise HanetAuthError(
                "HANET username and password are required for web discovery",
                status=401,
            )
        async with self._auth_lock:
            if self._web_authenticated:
                return
            session = await self._get_session()
            try:
                async with session.get(
                    urljoin(self.web_base_url, "api/auth/csrf"),
                    ssl=self.verify_tls,
                ) as response:
                    csrf_data = await response.json(content_type=None)
                csrf = (
                    csrf_data.get("csrfToken")
                    if isinstance(csrf_data, Mapping)
                    else None
                )
                if not csrf:
                    raise HanetAuthError(
                        "HANET web login did not return a CSRF token",
                        status=401,
                    )
                async with session.post(
                    urljoin(
                        self.web_base_url,
                        "api/auth/callback/credentials",
                    ),
                    data={
                        "csrfToken": csrf,
                        "username": self.username,
                        "password": self.password,
                        "callbackUrl": urljoin(self.web_base_url, "place"),
                        "redirect": "false",
                    },
                    allow_redirects=False,
                    ssl=self.verify_tls,
                ) as response:
                    if response.status not in {200, 302, 303}:
                        raise HanetAuthError(
                            "HANET web login was rejected",
                            status=response.status,
                        )
                async with session.get(
                    urljoin(self.web_base_url, "api/auth/session"),
                    ssl=self.verify_tls,
                ) as response:
                    web_session = await response.json(content_type=None)
                if not (
                    isinstance(web_session, Mapping)
                    and web_session.get("user")
                ):
                    raise HanetAuthError(
                        "HANET web session is not active",
                        status=401,
                    )
                self._web_authenticated = True
            except HanetApiError:
                raise
            except (TimeoutError, aiohttp.ClientError) as err:
                raise HanetApiError(
                    f"HANET web discovery failed: {type(err).__name__}"
                ) from err

    async def _web_html(self, path: str, *, retry: bool = True) -> str:
        if not path.startswith("/") or path.startswith("//"):
            raise HanetConfigurationError("HANET web paths must be relative")
        await self._web_login()
        session = await self._get_session()
        try:
            async with session.get(
                urljoin(self.web_base_url, path.lstrip("/")),
                headers={
                    "Accept": "text/html",
                    "User-Agent": "HANET-Connect-Home-Assistant/0.8.0",
                },
                allow_redirects=True,
                ssl=self.verify_tls,
            ) as response:
                if response.status in {401, 403} or "/login" in str(
                    response.url
                ).casefold():
                    if retry:
                        self._web_authenticated = False
                        return await self._web_html(path, retry=False)
                    raise HanetAuthError(
                        "HANET web session expired",
                        status=response.status,
                    )
                if response.status >= 400:
                    raise HanetApiError(
                        f"HANET web inventory returned HTTP {response.status}",
                        status=response.status,
                    )
                return await response.text()
        except HanetApiError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HanetApiError(
                f"HANET web inventory failed: {type(err).__name__}"
            ) from err

    async def _login_locked(self) -> Mapping[str, Any]:
        result = await self._request_direct(
            "POST",
            ENDPOINTS["auth_login"].path,
            payload={"username": self.username, "password": self.password},
            auth=False,
        )
        self._set_tokens(result)
        if not self.authenticated:
            raise HanetAuthError("HANET login response did not contain an access token", status=401)
        return result

    async def _refresh_locked(self) -> Mapping[str, Any]:
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise HanetAuthError("No HANET refresh token is available", status=401)
        result = await self._request_direct(
            "POST",
            ENDPOINTS["auth_refresh"].path,
            payload={"refresh_token": refresh_token},
            auth=False,
        )
        self._set_tokens(result, preserve_refresh=True)
        if not self.authenticated:
            raise HanetAuthError(
                "HANET refresh response did not contain an access token", status=401
            )
        return result

    def _set_tokens(self, response: Any, *, preserve_refresh: bool = False) -> None:
        found = _find_token_values(response)
        if preserve_refresh and not found.get("refresh_token"):
            found["refresh_token"] = self._tokens.get("refresh_token")
        access_token = found.get("access_token")
        if access_token:
            expires_at = _jwt_expiry(str(access_token))
            if expires_at is None and found.get("expires_in") is not None:
                try:
                    expires_at = time.time() + float(found["expires_in"])
                except (TypeError, ValueError):
                    expires_at = None
            found["expires_at"] = expires_at
            self._tokens = {key: value for key, value in found.items() if value is not None}
            if self._token_callback is not None:
                self._token_callback(dict(self._tokens))

    async def request_endpoint(
        self,
        endpoint_name: str,
        payload: Mapping[str, Any] | None = None,
        *,
        fields: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        """Call a catalog endpoint, trying the app-compatible method fallbacks."""
        spec = ENDPOINTS.get(endpoint_name)
        if spec is None:
            raise HanetConfigurationError(f"Unknown HANET endpoint: {endpoint_name}")
        payload = _normalize_identifier_payload(payload)
        if spec.auth:
            await self.authenticate()
        last_error: HanetApiError | None = None
        for index, method in enumerate(spec.methods):
            try:
                return await self._request_direct(
                    method,
                    spec.path,
                    payload=payload,
                    fields=fields,
                    files=files,
                    auth=spec.auth,
                    retry_auth=True,
                )
            except HanetApiError as err:
                last_error = err
                if index + 1 >= len(spec.methods) or not _can_try_next_method(method, err):
                    raise
                _LOGGER.debug(
                    "Retrying HANET endpoint %s with %s after HTTP %s",
                    endpoint_name,
                    spec.methods[index + 1],
                    err.status,
                )
        if last_error is not None:
            raise last_error
        raise HanetApiError(f"No HTTP method configured for {endpoint_name}")

    async def _request_direct(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        fields: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
        auth: bool,
        retry_auth: bool = False,
    ) -> Any:
        if not path.startswith("/") or path.startswith("//"):
            raise HanetConfigurationError("HANET API paths must be absolute same-origin paths")
        session = await self._get_session()
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = {
            "Accept": "application/json, text/event-stream;q=0.9",
            "User-Agent": "HANET-Connect-Home-Assistant/0.8.0",
        }
        if auth and self._tokens.get("access_token"):
            headers["Authorization"] = f"Bearer {self._tokens['access_token']}"
        kwargs: dict[str, Any] = {"headers": headers, "ssl": self.verify_tls}
        if files or fields:
            form = aiohttp.FormData()
            for key, value in (fields or {}).items():
                form.add_field(str(key), "" if value is None else str(value))
            for key, (filename, content, content_type) in (files or {}).items():
                form.add_field(
                    str(key),
                    content,
                    filename=filename,
                    content_type=content_type or "application/octet-stream",
                )
            kwargs["data"] = form
        elif method == "GET":
            kwargs["params"] = _query_payload(payload)
        elif payload is not None:
            kwargs["json"] = dict(payload)

        try:
            async with session.request(method, url, **kwargs) as response:
                result = await _decode_response(response)
                if response.status == 401 and auth and retry_auth:
                    await self.authenticate(force=True)
                    return await self._request_direct(
                        method,
                        path,
                        payload=payload,
                        fields=fields,
                        files=files,
                        auth=auth,
                        retry_auth=False,
                    )
                if response.status >= 400:
                    raise _api_error(response.status, result)
                return result
        except TimeoutError as err:
            raise HanetApiError("HANET API request timed out") from err
        except aiohttp.ClientError as err:
            raise HanetApiError(f"HANET API connection failed: {type(err).__name__}") from err

    async def iter_events(
        self,
        *,
        endpoint_name: str = "event_stream",
        payload: Mapping[str, Any] | None = None,
        last_event_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed server-sent events from HANET."""
        spec = ENDPOINTS.get(endpoint_name)
        if spec is None or spec.methods != ("POST",):
            raise HanetConfigurationError("Endpoint is not a realtime POST stream")
        await self.authenticate()
        session = await self._get_session()
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Authorization": f"Bearer {self._tokens['access_token']}",
            "User-Agent": "HANET-Connect-Home-Assistant/0.8.0",
        }
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        url = urljoin(self.base_url, spec.path.lstrip("/"))
        async with session.post(
            url,
            headers=headers,
            json=_normalize_identifier_payload(payload) or {},
            ssl=self.verify_tls,
            timeout=aiohttp.ClientTimeout(total=None, connect=15, sock_read=90),
        ) as response:
            if response.status >= 400:
                raise _api_error(response.status, await _decode_response(response))
            event: dict[str, Any] = {"event": "message", "data": ""}
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    if event.get("data"):
                        event["data"] = _decode_event_data(str(event["data"]))
                        yield event
                    event = {"event": "message", "data": ""}
                    continue
                if line.startswith(":"):
                    continue
                field, separator, value = line.partition(":")
                if not separator:
                    continue
                value = value.lstrip(" ")
                if field == "data":
                    event["data"] = f"{event.get('data', '')}\n{value}".lstrip("\n")
                elif field in {"event", "id", "retry"}:
                    event[field] = value

    async def fetch_media(self, url: str, *, limit: int = 12 * 1024 * 1024) -> tuple[bytes, str]:
        """Fetch a HANET-hosted image/media object with a size limit."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        api_hostname = (urlparse(self.base_url).hostname or "").lower()
        if parsed.scheme not in {"https", "http"} or not (
            hostname == api_hostname or hostname.endswith(".hanet.ai")
        ):
            raise HanetConfigurationError("Media URL is outside the HANET domains")
        session = await self._get_session()
        headers = _media_headers(
            hostname, api_hostname, self._tokens.get("access_token")
        )
        async with session.get(url, headers=headers, ssl=self.verify_tls) as response:
            if response.status >= 400:
                raise _api_error(response.status, await _decode_response(response))
            size = response.content_length
            if size is not None and size > limit:
                raise HanetApiError("HANET media response is too large", status=413)
            body = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                body.extend(chunk)
                if len(body) > limit:
                    raise HanetApiError("HANET media response is too large", status=413)
            return bytes(body), response.content_type or "application/octet-stream"


def _find_token_values(value: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    queue = [value]
    visited: set[int] = set()
    while queue:
        current = queue.pop(0)
        if isinstance(current, Mapping):
            if id(current) in visited:
                continue
            visited.add(id(current))
            for target, variants in _TOKEN_KEYS.items():
                for key in variants:
                    if current.get(key) is not None and target not in found:
                        found[target] = current[key]
                        break
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return found


def _next_rsc_text(html: str) -> str:
    """Join Next.js server-component chunks embedded by connect.hanet.ai."""
    chunks: list[str] = []
    for raw in re.findall(
        r"self\.__next_f\.push\((\[.*?\])\)</script>",
        html,
        re.DOTALL,
    ):
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(item, list)
            and len(item) >= 2
            and item[0] == 1
            and isinstance(item[1], str)
        ):
            chunks.append(item[1])
    return "".join(chunks)


def _matching_brace(text: str, start: int) -> int | None:
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _rsc_objects_with_key(text: str, key: str) -> list[dict[str, Any]]:
    """Extract JSON objects with a known key from a Next.js RSC stream."""
    found: dict[str, dict[str, Any]] = {}
    needle = f'"{key}":'
    cursor = 0
    while (position := text.find(needle, cursor)) >= 0:
        cursor = position + len(needle)
        base = max(0, position - 5000)
        openings = [
            match.start() + base
            for match in re.finditer(r"\{", text[base:position])
        ]
        for start in reversed(openings):
            end = _matching_brace(text, start)
            if end is None or end < position:
                continue
            try:
                value = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict) or key not in value:
                continue
            identity = json.dumps(
                [value.get(key), value.get("id"), value.get("place_id")],
                sort_keys=True,
                default=str,
            )
            found[identity] = value
            break
    return list(found.values())


def _media_headers(hostname: str, api_hostname: str, token: Any) -> dict[str, str]:
    """Keep API authorization away from static object-storage hosts."""
    headers = {"User-Agent": "HANET-Connect-Home-Assistant/0.8.0"}
    if hostname == api_hostname and token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _jwt_expiry(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return float(decoded["exp"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _query_payload(payload: Mapping[str, Any] | None) -> list[tuple[str, str]] | None:
    if not payload:
        return None
    output: list[tuple[str, str]] = []
    for key, value in payload.items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple, set)) else (value,)
        for item in values:
            if isinstance(item, bool):
                rendered = "true" if item else "false"
            elif isinstance(item, (dict, list)):
                rendered = json.dumps(item, separators=(",", ":"))
            else:
                rendered = str(item)
            output.append((str(key), rendered))
    return output


def _normalize_identifier_payload(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Restore numeric database IDs after HA-safe string normalization."""
    if payload is None:
        return None
    return {
        str(key): _normalize_identifier_value(str(key), value)
        for key, value in payload.items()
    }


def _normalize_identifier_value(key: str, value: Any) -> Any:
    canonical = key.replace("_", "").lower()
    if isinstance(value, Mapping):
        return {
            str(nested_key): _normalize_identifier_value(str(nested_key), nested)
            for nested_key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        if canonical in _NUMERIC_IDENTIFIER_KEYS:
            return [_numeric_string_to_int(item) for item in value]
        return list(value)
    if canonical in _NUMERIC_IDENTIFIER_KEYS:
        return _numeric_string_to_int(value)
    return value


def _numeric_string_to_int(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    try:
        return int(stripped, 10)
    except ValueError:
        return value


async def _decode_response(response: aiohttp.ClientResponse) -> Any:
    body = await response.read()
    if not body:
        return {}
    text = body.decode(response.charset or "utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _api_error(status: int, payload: Any) -> HanetApiError:
    message = f"HANET API returned HTTP {status}"
    code: int | str | None = None
    field: str | None = None
    if isinstance(payload, Mapping):
        message = str(payload.get("message") or payload.get("error") or message)
        code = payload.get("code")
        raw_field = payload.get("field")
        field = str(raw_field) if raw_field is not None else None
    elif isinstance(payload, str) and payload.strip():
        message = payload.strip()[:500]
    error_type = HanetAuthError if status in {401, 403} else HanetApiError
    return error_type(message, status=status, code=code, field=field, payload=payload)


def _can_try_next_method(method: str, error: HanetApiError) -> bool:
    if error.status in {404, 405, 415}:
        return True
    return bool(method == "GET" and error.status == 400)


def _decode_event_data(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def endpoint_catalog() -> list[dict[str, object]]:
    """Return the sorted public API catalog."""
    return [ENDPOINTS[name].public_dict() for name in sorted(ENDPOINTS)]
