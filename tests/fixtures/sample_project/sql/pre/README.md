# sql/pre

Everything in `sql/pre/` runs **before** every migration step (both the base
bootstrap and every incremental). Files here **must be idempotent and immutable**
across releases. Treat them like a header that ships with every migration.
