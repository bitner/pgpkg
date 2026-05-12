from __future__ import annotations

from pgpkg.diff import _strip_unsafe_routine_drops


def test_strip_unsafe_routine_drops_keeps_needed_drop() -> None:
    diff_sql = "\n".join(
        [
            'drop function if exists "sampleext"."f"(integer);',
            'drop function if exists "sampleext"."g"(text);',
            "create table sampleext.t(id int);",
        ]
    )

    target_sigs = {("function", "sampleext.f(integer)")}

    out = _strip_unsafe_routine_drops(diff_sql, target_sigs)

    assert 'drop function if exists "sampleext"."f"(integer);' not in out
    assert 'drop function if exists "sampleext"."g"(text);' in out
    assert "create table sampleext.t(id int);" in out


def test_strip_unsafe_routine_drops_keeps_drop_when_kind_changes() -> None:
    diff_sql = 'drop function if exists "sampleext"."f"(integer);'

    target_sigs = {("procedure", "sampleext.f(integer)")}

    out = _strip_unsafe_routine_drops(diff_sql, target_sigs)

    assert 'drop function if exists "sampleext"."f"(integer);' in out


def test_strip_unsafe_routine_drops_keeps_drop_for_case_sensitive_name() -> None:
    diff_sql = 'drop function if exists "sampleext"."camelcase"(integer);'

    target_sigs = {("function", "sampleext.CamelCase(integer)")}

    out = _strip_unsafe_routine_drops(diff_sql, target_sigs)

    assert 'drop function if exists "sampleext"."camelcase"(integer);' in out
