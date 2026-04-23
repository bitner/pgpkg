"""Filename grammar and fragment ordering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import LayoutError
from .versioning import UNRELEASED, parse

# Matches `<prefix>--<version>.sql` or `<prefix>--<from>--<to>.sql`
# Versions are PEP 440 OR literal 'unreleased'.
_VERSION_RE = r"(?:unreleased|[0-9][A-Za-z0-9.+!\-]*)"
_BASE_RE = re.compile(rf"^(?P<prefix>[A-Za-z0-9_]+)--(?P<version>{_VERSION_RE})\.sql$")
_INC_RE = re.compile(
    rf"^(?P<prefix>[A-Za-z0-9_]+)--(?P<from>{_VERSION_RE})--(?P<to>{_VERSION_RE})\.sql$"
)


@dataclass(frozen=True)
class BaseFilename:
    prefix: str
    version: str
    path: Path


@dataclass(frozen=True)
class IncrementalFilename:
    prefix: str
    from_version: str
    to_version: str
    path: Path


def parse_migration_filename(path: Path) -> BaseFilename | IncrementalFilename:
    """Parse a migrations/ filename into a typed record."""
    name = path.name
    # Try incremental first because base also matches the leading prefix.
    m = _INC_RE.match(name)
    if m:
        from_v = m.group("from")
        to_v = m.group("to")
        _validate_version(from_v, name)
        _validate_version(to_v, name)
        return IncrementalFilename(
            prefix=m.group("prefix"),
            from_version=from_v,
            to_version=to_v,
            path=path,
        )
    m = _BASE_RE.match(name)
    if m:
        version = m.group("version")
        _validate_version(version, name)
        return BaseFilename(
            prefix=m.group("prefix"),
            version=version,
            path=path,
        )
    raise LayoutError(f"Unrecognized migration filename: {name}")


def _validate_version(version: str, filename: str) -> None:
    if version == UNRELEASED:
        return
    try:
        parse(version)
    except Exception as exc:
        raise LayoutError(f"Invalid version {version!r} in {filename}") from exc


def base_filename(prefix: str, version: str) -> str:
    return f"{prefix}--{version}.sql"


def incremental_filename(prefix: str, from_v: str, to_v: str) -> str:
    return f"{prefix}--{from_v}--{to_v}.sql"


def sorted_fragments(directory: Path) -> list[Path]:
    """Return *.sql files in a directory, sorted by name (excludes subdirs)."""
    if not directory.exists():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".sql")
