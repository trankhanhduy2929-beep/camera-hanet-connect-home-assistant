"""HANET cloud P2P media bridge."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import platform
import shutil
import sys
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ._cloud_api import HanetApiClient
from ._errors import HanetApiError

_LOGGER = logging.getLogger(__name__)
_CREDENTIAL_TTL = 45
_SNAPSHOT_TTL = 10
_STREAM_IDLE_SECONDS = 8
_STREAM_QUEUE_SIZE = 4
_FIRST_FRAME_TIMEOUT = 22
_STREAM_START_ATTEMPTS = 2
_MJPEG_BOUNDARY = b"--frame\r\n"
_VENDOR_ROOT = Path(__file__).with_name("vendor") / "tutk"
_GCOMPAT_ROOT = Path(__file__).with_name("vendor") / "gcompat"
_CONTROL_IDLE_SECONDS = 20
_PTZ_COMMANDS = {
    "stop",
    "up",
    "down",
    "left",
    "leftUp",
    "leftDown",
    "right",
    "rightUp",
    "rightDown",
    "autoScan",
    "presetSet",
    "presetGo",
    "zoomIn",
    "zoomOut",
}


@dataclass(frozen=True, slots=True, repr=False)
class P2PCloudCredentials:
    """Short-lived P2P credentials that must never enter public state."""

    uid: str
    username: str
    password: str
    license_key: str

    def worker_payload(self, *, mode: str = "stream") -> bytes:
        return (
            json.dumps(
                {
                    "uid": self.uid,
                    "username": self.username,
                    "password": self.password,
                    "license_key": self.license_key,
                    "quality": 2,
                    "mode": mode,
                },
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )


@dataclass(eq=False, slots=True)
class MediaPipeline:
    """One native P2P reader feeding one FFmpeg transcoder."""

    worker: asyncio.subprocess.Process
    transcoder: asyncio.subprocess.Process
    relay_task: asyncio.Task[None]
    device_id: str

    @property
    def stdout(self) -> asyncio.StreamReader | None:
        return self.transcoder.stdout


@dataclass(eq=False, slots=True)
class MjpegSubscription:
    """One HTTP viewer subscribed to a shared camera stream."""

    session: SharedMjpegSession
    queue: asyncio.Queue[bytes | None]
    closed: bool = False

    async def read(self) -> bytes:
        if self.closed:
            return b""
        chunk = await self.queue.get()
        if chunk is None:
            self.closed = True
            return b""
        return chunk


@dataclass(eq=False, slots=True)
class SharedMjpegSession:
    """A single P2P/FFmpeg pipeline shared by every viewer of one camera."""

    device_id: str
    pipeline: MediaPipeline
    subscribers: set[MjpegSubscription] = field(default_factory=set)
    frame_event: asyncio.Event = field(default_factory=asyncio.Event)
    broadcaster: asyncio.Task[None] | None = None
    idle_task: asyncio.Task[None] | None = None
    latest_part: bytes = b""
    latest_jpeg: bytes = b""
    error_code: str = ""
    closed: bool = False


@dataclass(eq=False, slots=True)
class P2PControlSession:
    """One reusable native P2P control channel."""

    process: asyncio.subprocess.Process
    idle_task: asyncio.Task[None] | None = None


class MediaBridge:
    """Convert remote HANET TUTK P2P video into browser-friendly media."""

    def __init__(self, client: HanetApiClient) -> None:
        self.client = client
        self._credentials: dict[str, tuple[float, P2PCloudCredentials]] = {}
        self._snapshot_cache: dict[str, tuple[float, bytes, str]] = {}
        self._pipelines: set[MediaPipeline] = set()
        self._device_locks: dict[str, asyncio.Lock] = {}
        self._streams: dict[str, SharedMjpegSession] = {}
        self._controls: dict[str, P2PControlSession] = {}
        self._control_locks: dict[str, asyncio.Lock] = {}

    async def close(self) -> None:
        """Terminate native sessions and forget all ephemeral credentials."""
        sessions = tuple(self._streams.values())
        await asyncio.gather(
            *(self._shutdown_stream(session) for session in sessions),
            return_exceptions=True,
        )
        pipelines = tuple(self._pipelines)
        await asyncio.gather(
            *(self.stop_process(pipeline) for pipeline in pipelines),
            return_exceptions=True,
        )
        controls = tuple(self._controls.items())
        await asyncio.gather(
            *(
                self._stop_control(device_id, session)
                for device_id, session in controls
            ),
            return_exceptions=True,
        )
        self._credentials.clear()
        self._snapshot_cache.clear()
        self._device_locks.clear()
        self._streams.clear()
        self._controls.clear()
        self._control_locks.clear()

    async def descriptor(
        self, device: Mapping[str, Any], *, probe: bool = True
    ) -> dict[str, Any]:
        """Return a credential-free P2P media descriptor for the frontend."""
        device_id = str(device.get("id") or "")
        rtsp_enabled = _truthy(_device_media_value(device, "rtsp_enable", "rtspEnable"))
        output: dict[str, Any] = {
            "device_id": device_id,
            "technology": "hanet_p2p",
            "transport": "TUTK P2P",
            "rtsp_enabled": rtsp_enabled,
            "snapshot_url": f"api/devices/{quote(device_id, safe='')}/image",
            "live_url": f"api/devices/{quote(device_id, safe='')}/live.mjpeg",
            "available": False,
            "code": "p2p_runtime_missing",
            "active": False,
            "viewers": 0,
        }
        session = self._streams.get(device_id)
        if session is not None and not session.closed:
            output["active"] = True
            output["viewers"] = len(session.subscribers)
        if not shutil.which("ffmpeg"):
            output["code"] = "media_tools_missing"
            return output
        if not _native_runtime_available():
            return output
        if probe:
            try:
                await self._p2p_credentials(device_id)
            except HanetApiError as err:
                output["code"] = err.code or "p2p_credentials_unavailable"
                return output
        output["available"] = True
        output["code"] = "ready"
        return output

    async def snapshot(
        self, device: Mapping[str, Any], events: Iterable[Mapping[str, Any]]
    ) -> tuple[bytes, str] | None:
        """Get an event image or capture a current frame over P2P."""
        device_id = str(device.get("id") or "")
        cached = self._snapshot_cache.get(device_id)
        if cached and time.monotonic() - cached[0] < _SNAPSHOT_TTL:
            return cached[1], cached[2]

        session = self._streams.get(device_id)
        if session is not None and not session.closed:
            if not session.latest_jpeg:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(session.frame_event.wait(), timeout=5)
            if session.latest_jpeg:
                return session.latest_jpeg, "image/jpeg"

        urls: list[str] = []
        if device.get("snapshot_url"):
            urls.append(str(device["snapshot_url"]))
        for event in events:
            event_device = str(event.get("device_id") or "")
            if event_device and event_device != device_id:
                continue
            image_url = event.get("image_url")
            if image_url:
                urls.append(str(image_url))
                break
        for url in urls:
            try:
                body, content_type = await self.client.fetch_media(url)
                if content_type.startswith("image/"):
                    self._snapshot_cache[device_id] = (
                        time.monotonic(),
                        body,
                        content_type,
                    )
                    return body, content_type
            except HanetApiError as err:
                _LOGGER.debug("HANET event image failed for %s: %s", device_id, err)

        if not shutil.which("ffmpeg") or not _native_runtime_available():
            return None
        try:
            credentials = await self._p2p_credentials(device_id)
        except HanetApiError:
            return None
        async with self._device_lock(device_id):
            session = self._streams.get(device_id)
            if session is not None and not session.closed:
                if session.latest_jpeg:
                    return session.latest_jpeg, "image/jpeg"
                return None
            pipeline = await self._start_pipeline(
                credentials, snapshot=True, device_id=device_id
            )
            try:
                assert pipeline.stdout is not None
                result = await asyncio.wait_for(pipeline.stdout.read(), timeout=25)
                if result.startswith(b"\xff\xd8"):
                    self._snapshot_cache[device_id] = (
                        time.monotonic(),
                        result,
                        "image/jpeg",
                    )
                    return result, "image/jpeg"
                return None
            except TimeoutError:
                return None
            finally:
                await self.stop_process(pipeline)
                self._credentials.pop(device_id, None)

    async def start_mjpeg(
        self, device: Mapping[str, Any]
    ) -> tuple[MjpegSubscription, bytes]:
        """Subscribe a viewer to the camera's shared remote P2P stream."""
        if not shutil.which("ffmpeg"):
            raise HanetApiError(
                _media_message("media_tools_missing"),
                status=503,
                code="media_tools_missing",
            )
        if not _native_runtime_available():
            raise HanetApiError(
                _media_message("p2p_runtime_missing"),
                status=503,
                code="p2p_runtime_missing",
            )
        device_id = str(device.get("id") or "")
        last_code = "p2p_stream_unavailable"
        for attempt in range(_STREAM_START_ATTEMPTS):
            session = await self._shared_stream(device_id)
            try:
                await asyncio.wait_for(
                    session.frame_event.wait(), timeout=_FIRST_FRAME_TIMEOUT
                )
            except TimeoutError:
                last_code = "first_frame_timeout"
                session.error_code = last_code
                await self._shutdown_stream(session)
            else:
                if not session.closed and session.latest_part:
                    if session.idle_task is not None:
                        session.idle_task.cancel()
                        session.idle_task = None
                    subscription = MjpegSubscription(
                        session=session,
                        queue=asyncio.Queue(maxsize=_STREAM_QUEUE_SIZE),
                    )
                    session.subscribers.add(subscription)
                    subscription.queue.put_nowait(session.latest_part)
                    return subscription, await subscription.read()
                last_code = session.error_code or last_code

            self._credentials.pop(device_id, None)
            if attempt + 1 < _STREAM_START_ATTEMPTS:
                _LOGGER.info(
                    "Retrying HANET P2P stream for %s after %s",
                    device_id,
                    last_code,
                )
                await asyncio.sleep(0.5)

        status = 504 if last_code == "first_frame_timeout" else 503
        raise HanetApiError(_media_message(last_code), status=status, code=last_code)

    async def stop_mjpeg(self, subscription: MjpegSubscription) -> None:
        """Detach one viewer and stop the native session after a short grace period."""
        subscription.closed = True
        session = subscription.session
        session.subscribers.discard(subscription)
        if session.subscribers or session.closed:
            return
        if session.idle_task is None or session.idle_task.done():
            session.idle_task = asyncio.create_task(
                self._stop_idle_stream(session),
                name=f"hanet-p2p-idle-{session.device_id}",
            )

    async def send_ptz(
        self, device: Mapping[str, Any], command: str
    ) -> dict[str, Any]:
        """Send the same TUTK PTZ IOCTRL command used by the mobile app."""
        if command not in _PTZ_COMMANDS:
            raise HanetApiError(
                "Lenh PTZ HANET khong duoc ho tro",
                status=400,
                code="invalid_ptz_command",
            )
        if not _native_runtime_available():
            raise HanetApiError(
                _media_message("p2p_runtime_missing"),
                status=503,
                code="p2p_runtime_missing",
            )
        device_id = str(device.get("id") or "")
        credentials = await self._p2p_credentials(device_id)
        lock = self._control_locks.setdefault(device_id, asyncio.Lock())
        async with lock:
            session = self._controls.get(device_id)
            if session is None or session.process.returncode is not None:
                session = await self._start_control(credentials, device_id)
                self._controls[device_id] = session
            if session.idle_task is not None:
                session.idle_task.cancel()
                session.idle_task = None
            process = session.process
            assert process.stdin is not None
            assert process.stdout is not None
            try:
                process.stdin.write(
                    json.dumps(
                        {"command": command}, separators=(",", ":")
                    ).encode()
                    + b"\n"
                )
                await process.stdin.drain()
                response = await asyncio.wait_for(
                    process.stdout.readline(), timeout=5
                )
            except (
                BrokenPipeError,
                ConnectionResetError,
                TimeoutError,
            ) as err:
                await self._stop_control(device_id, session)
                raise HanetApiError(
                    _media_message("p2p_control_unavailable"),
                    status=503,
                    code="p2p_control_unavailable",
                ) from err
            if response.strip() != b"OK":
                await self._stop_control(device_id, session)
                raise HanetApiError(
                    _media_message("p2p_control_rejected"),
                    status=502,
                    code="p2p_control_rejected",
                )
            session.idle_task = asyncio.create_task(
                self._stop_idle_control(device_id, session),
                name=f"hanet-p2p-control-idle-{device_id}",
            )
        return {
            "device_id": device_id,
            "command": command,
            "transport": "TUTK P2P",
        }

    async def stop_process(self, pipeline: MediaPipeline) -> None:
        """Stop FFmpeg and its isolated native P2P worker."""
        self._pipelines.discard(pipeline)
        worker_input = pipeline.worker.stdin
        if (
            pipeline.worker.returncode is None
            and worker_input is not None
            and not worker_input.is_closing()
        ):
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                worker_input.write(b"stop\n")
                await worker_input.drain()
            worker_input.close()

        await _wait_or_stop(pipeline.worker, timeout=4)
        try:
            await asyncio.wait_for(asyncio.shield(pipeline.relay_task), timeout=1)
        except TimeoutError:
            pipeline.relay_task.cancel()
            await asyncio.gather(pipeline.relay_task, return_exceptions=True)
        await _wait_or_stop(pipeline.transcoder, timeout=2)

    async def _shared_stream(self, device_id: str) -> SharedMjpegSession:
        lock = self._device_lock(device_id)
        async with lock:
            current = self._streams.get(device_id)
            if (
                current is not None
                and not current.closed
                and current.broadcaster is not None
                and not current.broadcaster.done()
            ):
                if current.idle_task is not None:
                    current.idle_task.cancel()
                    current.idle_task = None
                return current

            credentials = await self._p2p_credentials(device_id)
            pipeline = await self._start_pipeline(
                credentials, snapshot=False, device_id=device_id
            )
            session = SharedMjpegSession(device_id=device_id, pipeline=pipeline)
            self._streams[device_id] = session
            session.broadcaster = asyncio.create_task(
                self._broadcast_stream(session),
                name=f"hanet-p2p-broadcast-{device_id}",
            )
            _LOGGER.info("Starting shared HANET P2P stream for %s", device_id)
            return session

    async def _broadcast_stream(self, session: SharedMjpegSession) -> None:
        buffer = bytearray()
        try:
            source = session.pipeline.stdout
            assert source is not None
            while chunk := await source.read(64 * 1024):
                buffer.extend(chunk)
                while part := _take_mjpeg_part(buffer):
                    self._publish_mjpeg_part(session, part)
            if not session.latest_part:
                session.error_code = await _pipeline_error_code(session.pipeline)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            session.error_code = "p2p_stream_unavailable"
            _LOGGER.warning(
                "HANET P2P stream failed for %s: %s",
                session.device_id,
                type(err).__name__,
            )
        finally:
            session.frame_event.set()
            await self.stop_process(session.pipeline)
            self._credentials.pop(session.device_id, None)
            session.closed = True
            if self._streams.get(session.device_id) is session:
                self._streams.pop(session.device_id, None)
            if session.idle_task is not None:
                current = asyncio.current_task()
                if session.idle_task is not current:
                    session.idle_task.cancel()
            for subscription in tuple(session.subscribers):
                _queue_latest(subscription.queue, None)
            _LOGGER.info(
                "Stopped shared HANET P2P stream for %s", session.device_id
            )

    def _publish_mjpeg_part(
        self, session: SharedMjpegSession, part: bytes
    ) -> None:
        session.latest_part = part
        jpeg = _jpeg_from_mjpeg_part(part)
        if jpeg:
            session.latest_jpeg = jpeg
            self._snapshot_cache[session.device_id] = (
                time.monotonic(),
                jpeg,
                "image/jpeg",
            )
        if not session.frame_event.is_set():
            session.frame_event.set()
            _LOGGER.info("Shared HANET P2P stream ready for %s", session.device_id)
        for subscription in tuple(session.subscribers):
            _queue_latest(subscription.queue, part)

    async def _stop_idle_stream(self, session: SharedMjpegSession) -> None:
        try:
            await asyncio.sleep(_STREAM_IDLE_SECONDS)
            if not session.subscribers:
                await self._shutdown_stream(session)
        except asyncio.CancelledError:
            raise

    async def _shutdown_stream(self, session: SharedMjpegSession) -> None:
        task = session.broadcaster
        if task is None:
            await self.stop_process(session.pipeline)
            session.closed = True
            session.frame_event.set()
            if self._streams.get(session.device_id) is session:
                self._streams.pop(session.device_id, None)
            for subscription in tuple(session.subscribers):
                _queue_latest(subscription.queue, None)
            return
        if task is asyncio.current_task():
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _p2p_credentials(self, device_id: str) -> P2PCloudCredentials:
        if not device_id:
            raise HanetApiError(
                _media_message("p2p_credentials_unavailable"),
                status=400,
                code="p2p_credentials_unavailable",
            )
        cached = self._credentials.get(device_id)
        if cached and time.monotonic() - cached[0] < _CREDENTIAL_TTL:
            return cached[1]
        try:
            response = await self.client.request_endpoint(
                "device_p2p_stream", {"device_id": device_id}
            )
            credentials = _extract_p2p_credentials(response)
        except HanetApiError:
            raise
        except (TypeError, ValueError) as err:
            raise HanetApiError(
                _media_message("p2p_credentials_unavailable"),
                status=502,
                code="p2p_credentials_unavailable",
            ) from err
        self._credentials[device_id] = (time.monotonic(), credentials)
        return credentials

    async def _start_control(
        self, credentials: P2PCloudCredentials, device_id: str
    ) -> P2PControlSession:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            str(Path(__file__).with_name("p2p_worker.py")),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_worker_environment(),
        )
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(credentials.worker_payload(mode="control"))
        await process.stdin.drain()
        try:
            ready = await asyncio.wait_for(
                process.stdout.readline(), timeout=25
            )
        except TimeoutError as err:
            await _wait_or_stop(process, timeout=0)
            raise HanetApiError(
                _media_message("p2p_control_unavailable"),
                status=504,
                code="p2p_control_unavailable",
            ) from err
        if ready.strip() != b"READY":
            detail = await _process_error_code(process)
            await _wait_or_stop(process, timeout=0)
            raise HanetApiError(
                _media_message(detail or "p2p_control_unavailable"),
                status=503,
                code=detail or "p2p_control_unavailable",
            )
        _LOGGER.info("HANET P2P PTZ channel ready for %s", device_id)
        return P2PControlSession(process=process)

    async def _stop_idle_control(
        self, device_id: str, session: P2PControlSession
    ) -> None:
        try:
            await asyncio.sleep(_CONTROL_IDLE_SECONDS)
            lock = self._control_locks.setdefault(
                device_id, asyncio.Lock()
            )
            async with lock:
                if (
                    self._controls.get(device_id) is session
                    and session.idle_task is asyncio.current_task()
                ):
                    await self._stop_control(device_id, session)
        except asyncio.CancelledError:
            raise

    async def _stop_control(
        self, device_id: str, session: P2PControlSession
    ) -> None:
        if self._controls.get(device_id) is session:
            self._controls.pop(device_id, None)
        task = session.idle_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        process = session.process
        if process.stdin is not None and not process.stdin.is_closing():
            process.stdin.close()
        await _wait_or_stop(process, timeout=2)

    async def _start_pipeline(
        self,
        credentials: P2PCloudCredentials,
        *,
        snapshot: bool,
        device_id: str,
    ) -> MediaPipeline:
        worker = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            str(Path(__file__).with_name("p2p_worker.py")),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_worker_environment(),
        )
        assert worker.stdin is not None
        worker.stdin.write(credentials.worker_payload())
        await worker.stdin.drain()

        output_args = (
            (
                "-frames:v",
                "1",
                "-vf",
                "scale='min(1280,iw)':-2",
                "-q:v",
                "4",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
            )
            if snapshot
            else (
                "-vf",
                "fps=8,scale='min(1280,iw)':-2",
                "-q:v",
                "5",
                "-f",
                "mpjpeg",
                "-boundary_tag",
                "frame",
                "pipe:1",
            )
        )
        try:
            transcoder = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-probesize",
                "65536",
                "-analyzeduration",
                "0",
                "-f",
                "hevc",
                "-i",
                "pipe:0",
                "-an",
                *output_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception:
            if worker.returncode is None:
                worker.terminate()
                await worker.wait()
            raise
        assert worker.stdout is not None
        assert transcoder.stdin is not None
        relay = asyncio.create_task(
            _relay_stream(worker.stdout, transcoder.stdin), name="hanet-p2p-relay"
        )
        pipeline = MediaPipeline(
            worker,
            transcoder,
            relay,
            device_id=device_id,
        )
        self._pipelines.add(pipeline)
        return pipeline

    def _device_lock(self, device_id: str) -> asyncio.Lock:
        return self._device_locks.setdefault(device_id, asyncio.Lock())


def _extract_p2p_credentials(value: Any) -> P2PCloudCredentials:
    uid = _find_value(value, "uuid", "uid", "p2p_id", "p2pid")
    username = _find_value(value, "user", "username")
    password = _find_value(value, "password", "pwd")
    license_key = _find_value(value, "auth", "auth_key", "authkey", "license_key")
    rendered = tuple(str(item or "") for item in (uid, username, password, license_key))
    if not all(rendered[:3]):
        raise HanetApiError(
            _media_message("p2p_credentials_unavailable"),
            status=502,
            code="p2p_credentials_unavailable",
        )
    return P2PCloudCredentials(*rendered)


def _find_value(value: Any, *names: str) -> Any:
    wanted = {_canonical_key(name) for name in names}
    queue = [value]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if isinstance(current, Mapping):
            if id(current) in seen:
                continue
            seen.add(id(current))
            for key, nested in current.items():
                if _canonical_key(str(key)) in wanted and nested is not None and nested != "":
                    return nested
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return None


def _take_mjpeg_part(buffer: bytearray) -> bytes:
    start = buffer.find(_MJPEG_BOUNDARY)
    if start < 0:
        if len(buffer) > len(_MJPEG_BOUNDARY) * 2:
            del buffer[: -len(_MJPEG_BOUNDARY)]
        return b""
    if start:
        del buffer[:start]
    next_part = buffer.find(_MJPEG_BOUNDARY, len(_MJPEG_BOUNDARY))
    if next_part < 0:
        return b""
    part = bytes(buffer[:next_part])
    del buffer[:next_part]
    return part


def _jpeg_from_mjpeg_part(part: bytes) -> bytes:
    start = part.find(b"\xff\xd8")
    end = part.rfind(b"\xff\xd9")
    if start < 0 or end < start:
        return b""
    return part[start : end + 2]


def _queue_latest(queue: asyncio.Queue[bytes | None], item: bytes | None) -> None:
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(item)


async def _relay_stream(
    source: asyncio.StreamReader, destination: asyncio.StreamWriter
) -> None:
    try:
        while chunk := await source.read(64 * 1024):
            destination.write(chunk)
            await destination.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        destination.close()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            await destination.wait_closed()


async def _wait_or_stop(process: asyncio.subprocess.Process, *, timeout: float) -> None:
    if process.returncode is not None:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        return
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


async def _pipeline_error_code(pipeline: MediaPipeline) -> str:
    for process in (pipeline.worker, pipeline.transcoder):
        if process.stderr is None:
            continue
        try:
            raw = await asyncio.wait_for(process.stderr.read(16 * 1024), timeout=0.5)
        except TimeoutError:
            continue
        text = raw.decode("utf-8", "replace")
        marker = "P2P_ERROR "
        if marker in text:
            detail = text.rsplit(marker, 1)[1].splitlines()[0]
            return detail.split(":", 1)[0]
    return "p2p_stream_unavailable"


async def _process_error_code(process: asyncio.subprocess.Process) -> str:
    if process.stderr is None:
        return ""
    try:
        raw = await asyncio.wait_for(
            process.stderr.read(16 * 1024), timeout=0.5
        )
    except TimeoutError:
        return ""
    text = raw.decode("utf-8", "replace")
    marker = "P2P_ERROR "
    if marker not in text:
        return ""
    return text.rsplit(marker, 1)[1].splitlines()[0].split(":", 1)[0]


def _native_runtime_available() -> bool:
    if os.name == "nt":
        return all((_VENDOR_ROOT / name).is_file() for name in ("IOTCAPIs.dll", "AVAPIs.dll"))
    machine = platform.machine().lower()
    name = (
        "lib.amd64"
        if machine in {"x86_64", "amd64"}
        else "lib.arm64"
        if machine in {"aarch64", "arm64"}
        else "lib.arm"
        if machine.startswith("arm")
        else ""
    )
    if not name or not (_VENDOR_ROOT / name).is_file():
        return False
    return not _running_on_musl() or _musl_compat_directory() is not None


def _worker_environment() -> dict[str, str]:
    """Preload bundled glibc compatibility only in the isolated P2P worker."""
    environment = os.environ.copy()
    compat_directory = _musl_compat_directory()
    if compat_directory is None:
        return environment
    preload = str(compat_directory / "libgcompat.so.0")
    current_preload = environment.get("LD_PRELOAD")
    if current_preload:
        preload = os.pathsep.join((preload, current_preload))
    library_path = str(compat_directory)
    current_library_path = environment.get("LD_LIBRARY_PATH")
    if current_library_path:
        library_path = os.pathsep.join((library_path, current_library_path))
    environment["LD_PRELOAD"] = preload
    environment["LD_LIBRARY_PATH"] = library_path
    return environment


def _running_on_musl() -> bool:
    if os.name == "nt":
        return False
    libc_name, _version = platform.libc_ver()
    if libc_name.lower() == "musl":
        return True
    return any(Path("/lib").glob("ld-musl-*.so.1"))


def _musl_compat_directory() -> Path | None:
    if not _running_on_musl():
        return None
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        architecture = "amd64"
        loader = "ld-linux-x86-64.so.2"
    elif machine in {"aarch64", "arm64"}:
        architecture = "arm64"
        loader = "ld-linux-aarch64.so.1"
    elif machine.startswith("arm"):
        architecture = "arm"
        loader = "ld-linux-armhf.so.3"
    else:
        return None
    directory = _GCOMPAT_ROOT / architecture
    required = (
        loader,
        "libgcompat.so.0",
        "libobstack.so.1",
        "libucontext.so.1",
    )
    return directory if all((directory / name).is_file() for name in required) else None


def _device_media_value(device: Mapping[str, Any], *keys: str) -> Any:
    sources = (device.get("raw"), device.get("settings"), device)
    canonical = {_canonical_key(key) for key in keys}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            if _canonical_key(str(key)) in canonical and value is not None:
                return value
    return None


def _canonical_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes", "enabled"}
    return bool(value)


def _media_message(code: str) -> str:
    messages = {
        "media_tools_missing": "Home Assistant chua co bo chuyen doi video FFmpeg",
        "p2p_runtime_missing": "Home Assistant khong co thu vien P2P phu hop voi may chu nay",
        "p2p_credentials_unavailable": "HANET Cloud khong cap thong tin P2P cho camera",
        "missing_sdk_license": "HANET Cloud khong cap giay phep P2P",
        "sdk_license_failed": "Giay phep P2P HANET khong hop le",
        "p2p_connect_failed": "Khong the ket noi camera qua P2P HANET",
        "camera_login_failed": "Camera tu choi phien xem P2P",
        "first_frame_timeout": "Camera P2P khong gui hinh anh",
        "frame_receive_failed": "Phien P2P bi gian doan",
        "p2p_stream_unavailable": "Luong P2P HANET tam thoi khong kha dung",
        "p2p_control_unavailable": "Khong the mo kenh dieu khien P2P HANET",
        "p2p_control_rejected": "Camera tu choi lenh dieu khien P2P HANET",
    }
    return messages.get(code, messages["p2p_stream_unavailable"])
