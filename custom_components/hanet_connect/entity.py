"""Shared entities and dynamic discovery helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HanetCoordinator

EntityFactory = Callable[[Mapping[str, Any]], Iterable[Entity]]


class HanetEntity(CoordinatorEntity[HanetCoordinator]):
    """Base class for an entity backed by one HANET device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HanetCoordinator, device_id: str, suffix: str
    ) -> None:
        super().__init__(coordinator)
        self.device_id = str(device_id)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{self.device_id}_{suffix}"
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return this entity's current device data."""
        return self.coordinator.device(self.device_id) or {}

    @property
    def available(self) -> bool:
        """Report availability of data, independently of device connectivity."""
        return super().available and bool(self.device)

    @property
    def device_info(self) -> DeviceInfo:
        """Register the physical HANET device."""
        device = self.device
        firmware = _text(
            device.get("firmware")
            or device.get("firmware_version")
            or device.get("version")
        )
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.entry.entry_id}:{self.device_id}",
                )
            },
            name=_text(device.get("name")) or f"HANET {self.device_id}",
            manufacturer="HANET",
            model=_text(device.get("model")),
            serial_number=_text(device.get("serial")) or self.device_id,
            sw_version=firmware,
            configuration_url=self.coordinator.client.base_url,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose stable placement information without the raw cloud payload."""
        device = self.device
        return {
            key: value
            for key, value in {
                "place_id": device.get("place_id"),
                "place_name": device.get("place_name"),
                "serial": device.get("serial"),
            }.items()
            if value not in (None, "")
        }


def setup_dynamic_entities(
    coordinator: HanetCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: EntityFactory,
) -> Callable[[], None]:
    """Add entities when devices or newly discovered settings appear."""
    known: set[str] = set()

    @callback
    def discover() -> None:
        entities: list[Entity] = []
        for device in coordinator.devices:
            for entity in factory(device):
                unique_id = entity.unique_id
                if unique_id and unique_id not in known:
                    known.add(unique_id)
                    entities.append(entity)
        if entities:
            async_add_entities(entities)

    discover()
    return coordinator.async_add_listener(discover)


def setting_value(device: Mapping[str, Any], key: str) -> Any:
    """Return a normalized setting value."""
    settings = device.get("settings")
    if not isinstance(settings, Mapping):
        return None
    current: Any = settings
    for part in key.split("."):
        if not isinstance(current, Mapping):
            return None
        actual = next(
            (
                candidate
                for candidate in current
                if _canonical_key(str(candidate)) == _canonical_key(part)
            ),
            None,
        )
        if actual is None:
            return None
        current = current[actual]
    return current


def has_setting(device: Mapping[str, Any], key: str) -> bool:
    """Return whether the gateway discovered a setting on this model."""
    return setting_value(device, key) is not None


def as_bool(value: Any) -> bool:
    """Handle booleans represented by the mobile API as strings or numbers."""
    if isinstance(value, Mapping):
        value = next(
            (
                candidate
                for key, candidate in value.items()
                if _canonical_key(str(key)) in {"enable", "enabled", "active"}
            ),
            value,
        )
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "online",
            "enabled",
            "active",
        }
    return bool(value)


SETTING_LABELS = {
    "audiorecording": "Ghi âm",
    "camerarotate": "Tự động theo dõi",
    "continuousrecognition": "Nhận diện liên tục",
    "distance": "Khoảng cách nhận diện",
    "enableaudio": "Âm thanh luồng",
    "falldetection": "Phát hiện té ngã",
    "human": "Phát hiện người",
    "humannormal": "Nhận diện người",
    "humantime": "Thời gian giữa hai lần nhận diện",
    "ir": "Hồng ngoại",
    "led": "Đèn trạng thái",
    "mp4record": "Ghi hình",
    "mqttbind": "Liên kết MQTT",
    "mqttuse": "MQTT",
    "notificationdevice": "Thông báo thiết bị",
    "notificationdevicestatus": "Thông báo trạng thái",
    "notificationemployee": "Thông báo nhân viên",
    "notificationevent": "Thông báo sự kiện",
    "notificationhuman": "Thông báo có người",
    "notificationstranger": "Thông báo người lạ",
    "notificationvisitor": "Thông báo khách",
    "persondetection": "Phát hiện người",
    "petdetection": "Phát hiện thú cưng",
    "ptzenabled": "Điều khiển quay quét",
    "quality": "Chất lượng video",
    "recognitionarea": "Vùng nhận diện",
    "recognitiondistance": "Khoảng cách nhận diện",
    "recognitionlevel": "Mức nhận diện",
    "recognitionthreshold": "Ngưỡng nhận diện",
    "record": "Ghi hình",
    "reverse": "Lật hình",
    "rtspenable": "RTSP",
    "securitymode": "Chế độ an ninh",
    "sdfreesize": "Dung lượng thẻ nhớ còn trống",
    "sdspacesize": "Tổng dung lượng thẻ nhớ",
    "storage": "Lưu trữ",
    "volume": "Âm lượng",
    "wdr": "Bù sáng",
}
_SETTING_WORDS = {
    "active": "hoạt động",
    "alarm": "cảnh báo",
    "area": "vùng",
    "audio": "âm thanh",
    "auto": "tự động",
    "brightness": "độ sáng",
    "camera": "camera",
    "checkin": "chấm công",
    "continuous": "liên tục",
    "delay": "độ trễ",
    "detection": "phát hiện",
    "device": "thiết bị",
    "distance": "khoảng cách",
    "employee": "nhân viên",
    "enable": "bật",
    "enabled": "bật",
    "event": "sự kiện",
    "fall": "té ngã",
    "human": "người",
    "interval": "khoảng thời gian",
    "level": "mức",
    "light": "đèn",
    "mode": "chế độ",
    "notification": "thông báo",
    "person": "người",
    "pet": "thú cưng",
    "quality": "chất lượng",
    "recognition": "nhận diện",
    "record": "ghi hình",
    "recording": "ghi hình",
    "reverse": "lật hình",
    "rotate": "xoay",
    "security": "an ninh",
    "sensitivity": "độ nhạy",
    "sound": "âm thanh",
    "speed": "tốc độ",
    "status": "trạng thái",
    "storage": "lưu trữ",
    "stranger": "người lạ",
    "threshold": "ngưỡng",
    "time": "thời gian",
    "tracking": "theo dõi",
    "use": "sử dụng",
    "video": "video",
    "visitor": "khách",
    "voice": "giọng nói",
    "volume": "âm lượng",
}
_SENSITIVE_SETTING_KEYS = {
    "accesstoken",
    "authkey",
    "licensekey",
    "password",
    "p2ppassword",
    "refreshtoken",
    "secret",
    "token",
}
_READ_ONLY_SETTING_WORDS = {
    "capacity",
    "firmware",
    "freesize",
    "ip",
    "mac",
    "model",
    "serial",
    "spacesize",
    "total",
    "uid",
    "version",
}


def setting_leaves(
    device: Mapping[str, Any],
) -> list[tuple[tuple[str, ...], Any, str]]:
    """Return safe scalar setting paths with Vietnamese labels."""
    settings = device.get("settings")
    if not isinstance(settings, Mapping):
        return []
    output: list[tuple[tuple[str, ...], Any, str]] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if len(path) > 5:
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if _canonical_key(str(key)) in _SENSITIVE_SETTING_KEYS:
                    continue
                visit(child, (*path, str(key)))
            return
        if path and (
            value is None or isinstance(value, (bool, int, float, str))
        ):
            output.append((path, value, setting_label(path)))

    visit(settings, ())
    return output


def setting_label(path: tuple[str, ...]) -> str:
    """Translate a model-specific setting path into a readable name."""
    canonical = _canonical_key(path[-1])
    if known := SETTING_LABELS.get(canonical):
        return known
    words = (
        path[-1].replace("-", "_").replace(" ", "_").casefold().split("_")
    )
    translated = " ".join(
        _SETTING_WORDS.get(word, word.upper() if len(word) <= 4 else word)
        for word in words
        if word
    )
    return f"Thông số camera {translated}".strip()


def setting_is_writable(path: tuple[str, ...]) -> bool:
    """Exclude diagnostic values that the cloud only reports."""
    canonical_parts = {_canonical_key(part) for part in path}
    return not any(
        word in part
        for part in canonical_parts
        for word in _READ_ONLY_SETTING_WORDS
    )


def event_recognition(event: Mapping[str, Any]) -> str | None:
    """Classify the latest camera event as familiar or stranger."""
    kind = _canonical_key(str(event.get("kind") or ""))
    if kind in {"employee", "visitor"}:
        return "known"
    if kind == "stranger":
        return "stranger"
    if event.get("recognized") or event.get("person_id"):
        return "known"
    if kind in {"face", "human", "person", "checkin"}:
        return "stranger"
    return None


def _canonical_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None
