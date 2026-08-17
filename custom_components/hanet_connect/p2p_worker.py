"""Isolated HANET TUTK P2P video and control worker.

The worker receives short-lived cloud credentials over stdin and writes the
camera's Annex-B HEVC stream to stdout. In control mode it keeps one P2P
session open and accepts PTZ commands on stdin. Keeping the native SDK in a
child process prevents a failed camera session from taking down the gateway.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import platform
import signal
import struct
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATA_NOT_READY = -20012
_INCOMPLETE_FRAME = -20013
_LOST_FRAME = -20014
_RETRYABLE = {_DATA_NOT_READY, _INCOMPLETE_FRAME, _LOST_FRAME, -20015, -20016}
_STOP = False
_VENDOR_ROOT = Path(__file__).with_name("vendor") / "tutk"
_PTZ_CONTROLS = {
    "stop": 0,
    "up": 1,
    "down": 2,
    "left": 3,
    "leftUp": 4,
    "leftDown": 5,
    "right": 6,
    "rightUp": 7,
    "rightDown": 8,
    "autoScan": 9,
    "presetSet": 10,
    "presetGo": 12,
    "zoomIn": 16,
    "zoomOut": 17,
}


class P2PWorkerError(RuntimeError):
    """A safe-to-log P2P worker failure."""


@dataclass(frozen=True, slots=True, repr=False)
class P2PCredentials:
    """Ephemeral values returned by HANET's P2P endpoint."""

    uid: str
    username: str
    password: str
    license_key: str = ""
    quality: int = 2

    @classmethod
    def from_json(cls, value: Any) -> P2PCredentials:
        if not isinstance(value, dict):
            raise P2PWorkerError("invalid_credentials")
        uid = str(value.get("uid") or "").strip()
        username = str(value.get("username") or "").strip()
        password = str(value.get("password") or "")
        license_key = str(value.get("license_key") or "")
        if not uid or len(uid) > 128 or not username or len(username) > 128:
            raise P2PWorkerError("invalid_credentials")
        if not password or len(password) > 256 or len(license_key) > 4096:
            raise P2PWorkerError("invalid_credentials")
        try:
            quality = max(0, min(4, int(value.get("quality", 2))))
        except (TypeError, ValueError):
            quality = 2
        return cls(uid, username, password, license_key, quality)


class AVClientStartInConfig(ctypes.Structure):
    """TUTK AV client configuration used by current SDK builds."""

    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("iotc_session_id", ctypes.c_uint32),
        ("iotc_channel_id", ctypes.c_uint8),
        ("timeout_sec", ctypes.c_uint32),
        ("account_or_identity", ctypes.c_char_p),
        ("password_or_token", ctypes.c_char_p),
        ("resend", ctypes.c_int32),
        ("security_mode", ctypes.c_uint32),
        ("auth_type", ctypes.c_uint32),
        ("sync_recv_data", ctypes.c_int32),
    ]


class AVClientStartOutConfig(ctypes.Structure):
    """TUTK AV client result structure."""

    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("server_type", ctypes.c_uint32),
        ("resend", ctypes.c_int32),
        ("two_way_streaming", ctypes.c_int32),
        ("sync_recv_data", ctypes.c_int32),
        ("security_mode", ctypes.c_uint32),
    ]


class NativeTutk:
    """Minimal ctypes binding for the redistributable TUTK runtime."""

    def __init__(self) -> None:
        self._dll_directory: Any = None
        self.iotc, self.av = self._load()
        self._configure_signatures()

    def _load(self) -> tuple[ctypes.CDLL, ctypes.CDLL]:
        if os.name == "nt":
            if hasattr(os, "add_dll_directory"):
                self._dll_directory = os.add_dll_directory(str(_VENDOR_ROOT))
            iotc = ctypes.CDLL(str(_VENDOR_ROOT / "IOTCAPIs.dll"))
            av = ctypes.CDLL(str(_VENDOR_ROOT / "AVAPIs.dll"))
            return iotc, av

        machine = platform.machine().lower()
        if machine in {"x86_64", "amd64"}:
            filename = "lib.amd64"
        elif machine in {"aarch64", "arm64"}:
            filename = "lib.arm64"
        elif machine.startswith("arm"):
            filename = "lib.arm"
        else:
            raise P2PWorkerError("unsupported_architecture")
        mode = getattr(ctypes, "RTLD_GLOBAL", 0)
        library = ctypes.CDLL(str(_VENDOR_ROOT / filename), mode=mode)
        return library, library

    def _configure_signatures(self) -> None:
        self.iotc.IOTC_Initialize2.argtypes = [ctypes.c_uint16]
        self.iotc.IOTC_Initialize2.restype = ctypes.c_int
        self.iotc.IOTC_Get_SessionID.restype = ctypes.c_int
        self.iotc.IOTC_Connect_ByUID_Parallel.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.iotc.IOTC_Connect_ByUID_Parallel.restype = ctypes.c_int
        self.av.avInitialize.argtypes = [ctypes.c_int]
        self.av.avInitialize.restype = ctypes.c_int
        self.av.avSendIOCtrl.argtypes = [
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self.av.avSendIOCtrl.restype = ctypes.c_int
        self.av.avRecvFrameData2.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.av.avRecvFrameData2.restype = ctypes.c_int

    def set_license(self, value: str) -> None:
        setter = getattr(self.iotc, "TUTK_SDK_Set_License_Key", None)
        if setter is None:
            return
        if not value:
            raise P2PWorkerError("missing_sdk_license")
        setter.argtypes = [ctypes.c_char_p]
        setter.restype = ctypes.c_int
        result = setter(value.encode("ascii"))
        if result < 0:
            raise P2PWorkerError(f"sdk_license_failed:{result}")

    def initialize(self) -> None:
        result = self.iotc.IOTC_Initialize2(0)
        if result < 0:
            raise P2PWorkerError(f"iotc_initialize_failed:{result}")
        result = self.av.avInitialize(32)
        if result < 0:
            raise P2PWorkerError(f"av_initialize_failed:{result}")

    def connect(self, credentials: P2PCredentials) -> tuple[int, int]:
        sid = self.iotc.IOTC_Get_SessionID()
        if sid < 0:
            raise P2PWorkerError(f"session_allocate_failed:{sid}")
        result = self.iotc.IOTC_Connect_ByUID_Parallel(
            credentials.uid.encode("ascii"), sid
        )
        if result < 0:
            raise P2PWorkerError(f"p2p_connect_failed:{result}")
        av_index = self._start_av(sid, credentials)
        if av_index < 0:
            raise P2PWorkerError(f"camera_login_failed:{av_index}")
        return sid, av_index

    def _start_av(self, sid: int, credentials: P2PCredentials) -> int:
        modern = getattr(self.av, "avClientStartEx", None)
        if modern is not None:
            config = AVClientStartInConfig()
            config.cb = ctypes.sizeof(config)
            config.iotc_session_id = sid
            config.iotc_channel_id = 0
            config.timeout_sec = 15
            config.account_or_identity = credentials.username.encode("utf-8")
            config.password_or_token = credentials.password.encode("utf-8")
            config.resend = 1
            config.security_mode = 2
            output = AVClientStartOutConfig()
            output.cb = ctypes.sizeof(output)
            modern.argtypes = [
                ctypes.POINTER(AVClientStartInConfig),
                ctypes.POINTER(AVClientStartOutConfig),
            ]
            modern.restype = ctypes.c_int
            result = modern(ctypes.byref(config), ctypes.byref(output))
            if result >= 0:
                return result

        legacy = getattr(self.av, "avClientStart2", None)
        if legacy is None:
            return -20000
        legacy.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        legacy.restype = ctypes.c_int
        server_type = ctypes.c_uint()
        resend = ctypes.c_int(1)
        return legacy(
            sid,
            credentials.username.encode("utf-8"),
            credentials.password.encode("utf-8"),
            15_000,
            ctypes.byref(server_type),
            0,
            ctypes.byref(resend),
        )

    def send(self, av_index: int, command: int, payload: bytes) -> None:
        data = ctypes.create_string_buffer(payload)
        result = self.av.avSendIOCtrl(av_index, command, data, len(payload))
        if result < 0:
            raise P2PWorkerError(f"camera_command_failed:{command}:{result}")

    def close(self, sid: int, av_index: int) -> None:
        if av_index >= 0:
            with contextlib.suppress(Exception):
                self.send(av_index, 767, b"\0" * 8)
            with contextlib.suppress(Exception):
                self.av.avClientStop(av_index)
        if sid >= 0:
            with contextlib.suppress(Exception):
                self.iotc.IOTC_Session_Close(sid)
        with contextlib.suppress(Exception):
            self.av.avDeInitialize()
        with contextlib.suppress(Exception):
            self.iotc.IOTC_DeInitialize()


def _write_all(payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(sys.stdout.fileno(), view)
        if written <= 0:
            raise BrokenPipeError
        view = view[written:]


def stream(credentials: P2PCredentials) -> None:
    """Open one P2P session and emit complete HEVC frames."""
    native = NativeTutk()
    sid = -1
    av_index = -1
    native.set_license(credentials.license_key)
    native.initialize()
    try:
        sid, av_index = native.connect(credentials)
        native.send(av_index, 1462, bytes((0, 1, 0, 0)))
        native.send(av_index, 800, struct.pack("<IB3x", 0, credentials.quality))
        native.send(av_index, 511, b"\0" * 8)
        native.send(av_index, 4098, b"\0" * 8)
        print("P2P_STATUS connected", file=sys.stderr, flush=True)

        frame_buffer = ctypes.create_string_buffer(4 * 1024 * 1024)
        frame_info = ctypes.create_string_buffer(256)
        actual = ctypes.c_int()
        expected = ctypes.c_int()
        info_size = ctypes.c_int()
        frame_number = ctypes.c_uint()
        first_frame_deadline = time.monotonic() + 35
        last_frame = time.monotonic()
        last_iframe_request = last_frame
        frames = 0
        synchronized = False

        while not _STOP:
            result = native.av.avRecvFrameData2(
                av_index,
                frame_buffer,
                len(frame_buffer),
                ctypes.byref(actual),
                ctypes.byref(expected),
                frame_info,
                len(frame_info),
                ctypes.byref(info_size),
                ctypes.byref(frame_number),
            )
            if result > 0 and actual.value > 0:
                payload = frame_buffer.raw[: min(result, actual.value)]
                info = frame_info.raw[: info_size.value]
                is_keyframe = len(info) >= 3 and bool(info[2] & 0x01)
                if not synchronized and not is_keyframe:
                    now = time.monotonic()
                    if now - last_iframe_request >= 2:
                        native.send(av_index, 4098, b"\0" * 8)
                        last_iframe_request = now
                    continue
                if is_keyframe:
                    synchronized = True
                if synchronized and payload.startswith((b"\0\0\0\1", b"\0\0\1")):
                    _write_all(payload)
                    frames += 1
                    last_frame = time.monotonic()
                continue
            if result not in _RETRYABLE:
                raise P2PWorkerError(f"frame_receive_failed:{result}")
            now = time.monotonic()
            if result in {_INCOMPLETE_FRAME, _LOST_FRAME}:
                synchronized = False
            if not synchronized and now - last_iframe_request >= 2:
                native.send(av_index, 4098, b"\0" * 8)
                last_iframe_request = now
            if frames == 0 and now >= first_frame_deadline:
                raise P2PWorkerError("first_frame_timeout")
            if frames and now - last_frame > 20:
                native.send(av_index, 4098, b"\0" * 8)
                last_frame = now
            time.sleep(0.02)
    finally:
        native.close(sid, av_index)


def control(credentials: P2PCredentials) -> None:
    """Keep a P2P session open and relay APK-compatible PTZ commands."""
    native = NativeTutk()
    sid = -1
    av_index = -1
    native.set_license(credentials.license_key)
    native.initialize()
    try:
        sid, av_index = native.connect(credentials)
        sys.stdout.buffer.write(b"READY\n")
        sys.stdout.buffer.flush()
        print("P2P_STATUS control_connected", file=sys.stderr, flush=True)
        while not _STOP:
            raw = sys.stdin.buffer.readline(4097)
            if not raw:
                break
            try:
                request = json.loads(raw)
                command = str(request.get("command") or "")
                control_code = _PTZ_CONTROLS[command]
                native.send(av_index, 4097, str(control_code).encode("utf-8"))
                sys.stdout.buffer.write(b"OK\n")
                sys.stdout.buffer.flush()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                sys.stdout.buffer.write(b"ERROR invalid_command\n")
                sys.stdout.buffer.flush()
            except P2PWorkerError as err:
                sys.stdout.buffer.write(
                    f"ERROR {err}\n".encode("utf-8", "replace")
                )
                sys.stdout.buffer.flush()
    finally:
        if av_index >= 0:
            with contextlib.suppress(P2PWorkerError):
                native.send(av_index, 4097, b"0")
        native.close(sid, av_index)


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def _watch_parent() -> None:
    """Stop cleanly when the gateway closes or writes to the control pipe."""
    with contextlib.suppress(OSError):
        sys.stdin.buffer.readline()
    _stop(0, None)


def main() -> int:
    """Read one bounded JSON document without exposing secrets in argv."""
    if sys.argv[1:] == ["--probe-runtime"]:
        try:
            NativeTutk()
        except (OSError, P2PWorkerError) as err:
            print(f"P2P_ERROR {err}", file=sys.stderr, flush=True)
            return 2
        print("READY", flush=True)
        return 0
    if os.name == "nt":
        import msvcrt

        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    signal.signal(signal.SIGTERM, _stop)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _stop)
    try:
        raw = sys.stdin.buffer.readline(16 * 1024 + 1)
        if not raw or len(raw) > 16 * 1024:
            raise P2PWorkerError("invalid_credentials")
        request = json.loads(raw)
        credentials = P2PCredentials.from_json(request)
        if request.get("mode") == "control":
            control(credentials)
        else:
            threading.Thread(
                target=_watch_parent,
                name="p2p-parent-watch",
                daemon=True,
            ).start()
            stream(credentials)
        return 0
    except BrokenPipeError:
        return 0
    except (OSError, ValueError, json.JSONDecodeError, P2PWorkerError) as err:
        print(f"P2P_ERROR {err}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
