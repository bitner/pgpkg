from __future__ import annotations

import pytest

from pgpkg.versioning import (
    UNRELEASED,
    default_target,
    highest_released,
    sorted_versions,
    version_sort_key,
)


def test_sorted_versions_semver_order():
    assert sorted_versions(["0.2.0", "0.1.0", "0.10.0"]) == ["0.1.0", "0.2.0", "0.10.0"]


def test_unreleased_sorts_last():
    assert sorted_versions(["0.2.0", UNRELEASED, "0.1.0"]) == ["0.1.0", "0.2.0", UNRELEASED]


def test_sort_key_comparable():
    assert version_sort_key("0.1.0") < version_sort_key("0.2.0")
    assert version_sort_key("0.2.0") < version_sort_key(UNRELEASED)


def test_highest_released_excludes_unreleased():
    assert highest_released(["0.1.0", "0.2.0", UNRELEASED]) == "0.2.0"
    assert highest_released([UNRELEASED]) is None
    assert highest_released([]) is None


def test_default_target_prefers_unreleased():
    assert default_target(["0.1.0", "0.2.0", UNRELEASED]) == UNRELEASED
    assert default_target(["0.1.0", "0.2.0"]) == "0.2.0"
    assert default_target([]) is None


def test_invalid_version_raises():
    from pgpkg.errors import PgpkgError
    from pgpkg.versioning import parse

    with pytest.raises(PgpkgError):
        parse("not-a-version")
