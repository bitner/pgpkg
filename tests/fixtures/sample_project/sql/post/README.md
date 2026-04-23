# sql/post

Everything in `sql/post/` runs **after** every migration step. Files here
**must be idempotent and immutable** across releases. Typical uses: grants,
policy refreshes, materialized view refreshes.
