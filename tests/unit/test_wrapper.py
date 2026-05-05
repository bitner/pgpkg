from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.errors import PgpkgError
from pgpkg.wrapper import scaffold_wrapper


def test_scaffold_wrapper_rejects_custom_version_source(
    sample_project: Path,
    tmp_path: Path,
):
    (sample_project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.pgpkg]",
                'project_name = "sampleext"',
                'prefix = "sampleext"',
                'version_source = "sampleext.migrate:VersionSource"',
            ]
        )
    )

    with pytest.raises(PgpkgError, match="version_source"):
        scaffold_wrapper(
            sample_project,
            output_dir=tmp_path / "wrapper",
            cli_name="sampleext-migrator",
        )
