"""Camera entities for HANET devices."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from typing import Any

from aiohttp import web
from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HanetConfigEntry
from .api import HanetGatewayError
from .entity import HanetEntity, setup_dynamic_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HANET cameras."""
    coordinator = entry.runtime_data.coordinator

    def build(device: Mapping[str, Any]) -> list[Camera]:
        return [HanetCamera(coordinator, str(device["id"]))]

    entry.async_on_unload(
        setup_dynamic_entities(coordinator, async_add_entities, build)
    )


class HanetCamera(HanetEntity, Camera):
    """Expose snapshots and browser video from direct native P2P."""

    _attr_name = None
    _attr_translation_key = "camera"

    def __init__(self, coordinator: Any, device_id: str) -> None:
        super().__init__(coordinator, device_id, "camera")
        Camera.__init__(self)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the latest image available to the gateway."""
        try:
            body, content_type = await self.coordinator.client.async_image(
                self.device_id
            )
        except HanetGatewayError:
            return None
        if content_type.startswith("image/"):
            self.content_type = content_type
        return body

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Serve native TUTK P2P as browser-compatible MJPEG."""
        try:
            subscription, first = (
                await self.coordinator.client.async_open_live(self.device_id)
            )
        except HanetGatewayError as err:
            _LOGGER.warning(
                "Không thể mở luồng P2P HANET cho %s: %s",
                self.device_id,
                err,
            )
            with contextlib.suppress(ConnectionResetError):
                return await super().handle_async_mjpeg_stream(request)
            return None

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": (
                    "multipart/x-mixed-replace; boundary=frame"
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
        try:
            await response.prepare(request)
            for reconnect in range(4):
                try:
                    await response.write(first)
                    while chunk := await subscription.read():
                        await response.write(chunk)
                finally:
                    await self.coordinator.client.async_close_live(
                        subscription
                    )
                if reconnect >= 3:
                    break
                await asyncio.sleep(min(0.5 * (reconnect + 1), 1.5))
                try:
                    subscription, first = (
                        await self.coordinator.client.async_open_live(
                            self.device_id
                        )
                    )
                except HanetGatewayError:
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            await self.coordinator.client.async_close_live(subscription)
        with contextlib.suppress(
            BrokenPipeError,
            ConnectionResetError,
            RuntimeError,
        ):
            await response.write_eof()
        return response
