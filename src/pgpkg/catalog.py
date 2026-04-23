"""Discover and validate the migrations/ directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import CatalogError
from .layout import (
    BaseFilename,
    IncrementalFilename,
    parse_migration_filename,
)
from .versioning import sorted_versions


@dataclass(frozen=True)
class Catalog:
    """Discovered migrations.

    base_files: maps version -> Path of `<prefix>--<v>.sql`
    edges: list of (from_v, to_v, Path) for `<prefix>--<a>--<b>.sql`
    prefix: the file prefix observed in the directory (validated against config)
    """

    base_files: dict[str, Path]
    edges: list[tuple[str, str, Path]]
    prefix: str
    migrations_dir: Path

    @property
    def versions(self) -> list[str]:
        """All known versions, sorted (released first, then unreleased)."""
        seen: set[str] = set(self.base_files.keys())
        for from_v, to_v, _ in self.edges:
            seen.add(from_v)
            seen.add(to_v)
        return sorted_versions(list(seen))


def build_catalog(config) -> Catalog:  # type: ignore[no-untyped-def]
    """Discover *.sql files in the migrations directory and validate them."""
    from .config import ProjectConfig

    assert isinstance(config, ProjectConfig)

    mig_dir = config.migrations_dir
    if not mig_dir.exists():
        # Empty catalog is allowed (project hasn't staged anything yet).
        return Catalog(base_files={}, edges=[], prefix=config.prefix, migrations_dir=mig_dir)

    base_files: dict[str, Path] = {}
    edges: list[tuple[str, str, Path]] = []
    seen_edges: set[tuple[str, str]] = set()

    for path in sorted(mig_dir.iterdir()):
        if not path.is_file() or path.suffix != ".sql":
            continue
        parsed = parse_migration_filename(path)
        if parsed.prefix != config.prefix:
            raise CatalogError(
                f"File {path.name} has prefix {parsed.prefix!r} but project prefix is "
                f"{config.prefix!r}. Rename the file or update [tool.pgpkg].prefix."
            )
        if isinstance(parsed, BaseFilename):
            if parsed.version in base_files:
                raise CatalogError(
                    f"Duplicate base file for version {parsed.version!r}: "
                    f"{base_files[parsed.version].name} and {path.name}"
                )
            base_files[parsed.version] = path
        else:
            assert isinstance(parsed, IncrementalFilename)
            key = (parsed.from_version, parsed.to_version)
            if key in seen_edges:
                raise CatalogError(
                    f"Duplicate incremental file: {path.name}"
                )
            if parsed.from_version == parsed.to_version:
                raise CatalogError(
                    f"Self-loop incremental disallowed: {path.name}"
                )
            seen_edges.add(key)
            edges.append((parsed.from_version, parsed.to_version, path))

    return Catalog(
        base_files=base_files,
        edges=edges,
        prefix=config.prefix,
        migrations_dir=mig_dir,
    )
