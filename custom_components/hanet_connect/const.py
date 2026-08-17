"""Constants for the HANET Connect integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hanet_connect"
INTEGRATION_VERSION: Final = "1.0.1"
CONF_API_BASE: Final = "api_base_url"
CONF_LICENSE_KEY: Final = "license_key"
CONF_VERIFY_TLS: Final = "verify_tls"
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_API_BASE: Final = "https://api-camera3.hanet.ai/v4"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 3600
EVENT_TYPE: Final = "hanet_connect_event"

PLATFORMS: Final = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
)

BOOL_SETTINGS: Final[dict[str, str]] = {
    "led": "lightbulb",
    "wdr": "brightness-auto",
    "ir": "weather-night",
    "reverse": "flip-vertical",
    "record": "record-rec",
    "audio_recording": "microphone",
    "enable_audio": "volume-high",
    "continuous_recognition": "account-search",
    "camera_rotate": "axis-z-rotate-clockwise",
    "rtsp_enable": "video-wireless",
    "mqtt_bind": "access-point-network",
    "mqtt_use": "access-point-network",
    "ptz_enabled": "axis-arrow",
    "notification_device": "bell",
    "notification_device_status": "bell",
    "notification_employee": "bell",
    "notification_employee_checkin": "bell",
    "notification_event": "bell",
    "notification_event_checkin": "bell",
    "notification_human": "bell",
    "notification_stranger": "bell-alert",
    "notification_stranger_checkin": "bell-alert",
    "notification_visitor": "bell",
    "notification_voice_call": "phone-ring",
    "notification_alarm_voice": "alarm-light",
    "security_mode": "shield-home",
    "person_detection": "human",
    "pet_detection": "paw",
    "fall_detection": "human-cane",
}

BOOL_SETTING_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "record": (
        "record",
        "mp4_record",
        "record_enable",
        "save_video",
        "recording",
    ),
    "continuous_recognition": (
        "continuous_recognition",
        "human_normal",
        "recognition_continuous",
    ),
    "camera_rotate": (
        "camera_rotate",
        "ptz.human_tracing",
    ),
    "rtsp_enable": ("rtsp_enable", "rtsp"),
    "notification_device_status": (
        "notification_device_status",
        "notification_device.enable",
    ),
    "security_mode": ("safe_area.high_security_mode.enable",),
    "person_detection": ("human",),
    "pet_detection": ("pet_enable",),
    "fall_detection": ("fall_enable",),
}

NUMBER_SETTINGS: Final[dict[str, tuple[float, float, float]]] = {
    "recognition_distance": (0, 100, 1),
    "distance": (0, 100, 1),
    "recognition_level": (0, 100, 1),
    "recognition_threshold": (0, 100, 1),
    "human_time": (1, 3600, 1),
}

SELECT_SETTINGS: Final[dict[str, tuple[str, ...]]] = {
    "quality": ("480p", "720p", "1080p", "1440p"),
    "storage": ("off", "sd", "cloud"),
    "recognition_area": ("full", "center_half", "center_third"),
}

DEVICE_COMMANDS: Final = (
    "open_door",
    "close_door",
    "alarm",
    "stop_alarm",
    "up",
    "down",
    "left",
    "right",
    "leftUp",
    "rightUp",
    "leftDown",
    "rightDown",
    "zoomIn",
    "zoomOut",
    "autoScan",
    "stop",
    "presetSet",
    "presetGo",
)
