"""Version sorting: PEP 440 + literal 'unreleased' (always last)."""

from __future__ import annotations

from packaging.version import InvalidVersion, Version

UNRELEASED = "unreleased"


def is_unreleased(version: str) -> bool:
    return version == UNRELEASED


def parse(version: str) -> Version | None:
    """Return parsed PEP 440 Version, or None for 'unreleased'."""
    if version == UNRELEASED:
        return None
    try:
        return Version(version)
    except InvalidVersion as exc:
        from .errors import PgpkgError

        raise PgpkgError(
            f"Invalid version string {version!r}: must be PEP 440 or 'unreleased'",
            code="E_VERSION",
        ) from exc


def version_sort_key(version: str) -> tuple[int, Version | None]:
    """Sort key. 'unreleased' always sorts last."""
    if version == UNRELEASED:
        return (1, None)
    return (0, Version(version))


def sorted_versions(versions: list[str]) -> list[str]:
    return sorted(versions, key=version_sort_key)


def highest_released(versions: list[str]) -> str | None:
    """Return the highest version that is NOT 'unreleased', or None."""
    released = [v for v in versions if v != UNRELEASED]
    if not released:
        return None
    return max(released, key=version_sort_key)


def default_target(versions: list[str]) -> str | None:
    """unreleased if present, else highest released."""
    if UNRELEASED in versions:
        return UNRELEASED
    return highest_released(versions)
