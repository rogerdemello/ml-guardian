"""Application error types."""
from __future__ import annotations


class ConfigurationError(RuntimeError):
    """A setup/configuration problem (e.g. live mode without a DataHub).

    `detail` is a curated, user-safe message — the exception handler returns it
    to the client. Never put secrets or raw internals in it.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
