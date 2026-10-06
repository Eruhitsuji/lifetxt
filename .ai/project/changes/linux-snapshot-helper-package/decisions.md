# Decisions

Optional explicit build/install preserves dependency-light core and architecture-independent wheels. No package-manager extra, runtime compiler or PATH lookup. Owner accepted Linux-only feature and missing-helper denial in #1115. Independent review/merge/release remain pending. Rollback: remove helper/manifest with server stopped, then restart; chunk reads unavailable. No data migration.
