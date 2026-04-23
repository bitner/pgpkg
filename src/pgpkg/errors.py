"""Exception types."""

from __future__ import annotations


class PgpkgError(Exception):
    """Base class for all pgpkg errors."""

    code: str = "E_PGPKG"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ConfigError(PgpkgError):
    code = "E_CONFIG"


class LayoutError(PgpkgError):
    code = "E_LAYOUT"


class CatalogError(PgpkgError):
    code = "E_CATALOG"


class PlanError(PgpkgError):
    code = "E_PLAN"


class ExecutionError(PgpkgError):
    code = "E_EXEC"


class VerifyError(PgpkgError):
    code = "E_VERIFY"
