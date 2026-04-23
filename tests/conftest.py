from __future__ import annotations

import atexit
import os
import shutil
from pathlib import Path
from unittest import SkipTest

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Copy the sample_project fixture into a temp dir and return its path."""
    src = FIXTURES / "sample_project"
    dst = tmp_path / "sample_project"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture(scope="session")
def pg_url() -> str:
    """Return a postgres URL usable with results.temporary_local_db.

    If PGPKG_TEST_DB_URL is set, use it directly. Otherwise start a
    testcontainers postgres and use that. Skips if neither is available.
    """
    url = os.environ.get("PGPKG_TEST_DB_URL")
    if url:
        return url
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError as exc:
        raise SkipTest("testcontainers not installed and PGPKG_TEST_DB_URL not set") from exc

    container = PostgresContainer("postgres:17-alpine")
    container.start()
    url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    atexit.register(container.stop)
    return url


@pytest.fixture
def staged_project(sample_project: Path) -> Path:
    """Sample project with 0.1.0 and 0.2.0 staged as base files, plus a
    hand-crafted 0.1.0 -> 0.2.0 incremental file (so tests that walk the
    migration graph do not need `results` to be installed).
    """
    from pgpkg.api import stage_version

    # 0.1.0: only the schema file. Temporarily rename 020_functions.sql aside.
    aside = sample_project / "sql" / "020_functions.sql.bak"
    (sample_project / "sql" / "020_functions.sql").rename(aside)
    stage_version(sample_project, "0.1.0")
    aside.rename(sample_project / "sql" / "020_functions.sql")
    stage_version(sample_project, "0.2.0")

    func_body = (sample_project / "sql" / "020_functions.sql").read_text()
    incr = sample_project / "migrations" / "sampleext--0.1.0--0.2.0.sql"
    incr.write_text("-- pgpkg incremental 0.1.0 -> 0.2.0\n" + func_body)
    return sample_project
