"""Gateway exceptions."""

from __future__ import annotations

from typing import Any


class HanetError(Exception):
    """Base HANET exception."""


class HanetApiError(HanetError):
    """An error returned by the HANET API."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: int | str | None = None,
        field: str | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.field = field
        self.payload = payload

    @property
    def retryable(self) -> bool:
        """Return whether retrying later can reasonably succeed."""
        return self.status is None or self.status == 429 or self.status >= 500

    def as_dict(self) -> dict[str, Any]:
        """Return a secret-safe representation for API responses."""
        return {
            "message": str(self),
            "status": self.status,
            "code": self.code,
            "field": self.field,
            "retryable": self.retryable,
        }


class HanetAuthError(HanetApiError):
    """Authentication failed or expired."""


class HanetConfigurationError(HanetError):
    """Gateway configuration is invalid."""

