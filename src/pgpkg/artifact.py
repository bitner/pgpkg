"""Bake migrations + pre/post into a tar.zst with a sha256 manifest."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

import zstandard as zstd

from .config import ProjectConfig
from .errors import PgpkgError
from .layout import sorted_fragments

MANIFEST_NAME = "MANIFEST.json"


@dataclass(frozen=True)
class ArtifactEntry:
    name: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ArtifactManifest:
    project_name: str
    prefix: str
    entries: list[ArtifactEntry]
    tracking_schema: str = "pgpkg"
    tracking_table: str = "migrations"
    version_source: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "project_name": self.project_name,
                "prefix": self.prefix,
                "tracking_schema": self.tracking_schema,
                "tracking_table": self.tracking_table,
                "version_source": self.version_source,
                "entries": [
                    {"name": e.name, "sha256": e.sha256, "size": e.size} for e in self.entries
                ],
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, text: str) -> ArtifactManifest:
        data = json.loads(text)
        return cls(
            project_name=data["project_name"],
            prefix=data["prefix"],
            entries=[ArtifactEntry(**e) for e in data["entries"]],
            tracking_schema=data.get("tracking_schema", "pgpkg"),
            tracking_table=data.get("tracking_table", "migrations"),
            version_source=data.get("version_source"),
        )


def build_artifact(config: ProjectConfig, output_path: Path) -> Path:
    """Bundle migrations/ + sql/pre + sql/post + runtime config into a tar.zst.

    Layout inside the archive:
        MANIFEST.json
        migrations/<all *.sql>
        pre/<all *.sql>      (only files, no README)
        post/<all *.sql>
    """
    if not config.migrations_dir.exists():
        raise PgpkgError(f"No migrations/ directory at {config.migrations_dir}", code="E_ARTIFACT")

    files: list[tuple[str, bytes]] = []  # (archive_name, content)
    for p in sorted(config.migrations_dir.iterdir()):
        if p.is_file() and p.suffix == ".sql":
            files.append((f"migrations/{p.name}", p.read_bytes()))
    for p in sorted_fragments(config.pre_dir):
        files.append((f"pre/{p.name}", p.read_bytes()))
    for p in sorted_fragments(config.post_dir):
        files.append((f"post/{p.name}", p.read_bytes()))

    if not any(name.startswith("migrations/") for name, _ in files):
        raise PgpkgError(
            f"No staged migration files found in {config.migrations_dir}", code="E_ARTIFACT"
        )

    entries = [
        ArtifactEntry(
            name=name,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
        )
        for name, data in files
    ]
    manifest = ArtifactManifest(
        project_name=config.project_name,
        prefix=config.prefix,
        entries=entries,
        tracking_schema=config.tracking_schema,
        tracking_table=config.tracking_table,
        version_source=config.version_source,
    )

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        manifest_bytes = manifest.to_json().encode("utf-8")
        tar.addfile(_tar_info(MANIFEST_NAME, manifest_bytes), io.BytesIO(manifest_bytes))
        for name, data in files:
            tar.addfile(_tar_info(name, data), io.BytesIO(data))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cctx = zstd.ZstdCompressor(level=19)
    output_path.write_bytes(cctx.compress(tar_buf.getvalue()))
    return output_path


def _tar_info(name: str, data: bytes) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


@dataclass(frozen=True)
class LoadedArtifact:
    """Decompressed view of a tar.zst artifact, kept entirely in memory."""

    manifest: ArtifactManifest
    files: dict[str, bytes]  # archive_name -> bytes

    def migrations_files(self) -> dict[str, bytes]:
        return {n: d for n, d in self.files.items() if n.startswith("migrations/")}

    def pre_sql(self) -> str:
        parts = [d.decode("utf-8") for n, d in sorted(self.files.items()) if n.startswith("pre/")]
        return "\n".join(parts)

    def post_sql(self) -> str:
        parts = [d.decode("utf-8") for n, d in sorted(self.files.items()) if n.startswith("post/")]
        return "\n".join(parts)


def load_artifact(path: Path) -> LoadedArtifact:
    """Decompress + verify a tar.zst artifact built by `build_artifact`."""
    raw = path.read_bytes()
    dctx = zstd.ZstdDecompressor()
    tar_bytes = dctx.decompress(raw)
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        for member in tar:
            if not member.isfile():
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            files[member.name] = f.read()

    if MANIFEST_NAME not in files:
        raise PgpkgError(f"Artifact {path} has no {MANIFEST_NAME}", code="E_ARTIFACT")
    manifest = ArtifactManifest.from_json(files[MANIFEST_NAME].decode("utf-8"))

    # Integrity check
    for entry in manifest.entries:
        data = files.get(entry.name)
        if data is None:
            raise PgpkgError(f"Artifact {path} missing entry {entry.name}", code="E_ARTIFACT")
        sha = hashlib.sha256(data).hexdigest()
        if sha != entry.sha256:
            raise PgpkgError(
                f"Artifact {path} entry {entry.name} sha256 mismatch", code="E_ARTIFACT"
            )

    return LoadedArtifact(manifest=manifest, files=files)
