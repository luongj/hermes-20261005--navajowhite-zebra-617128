---
name: artifact-ingest
description: "Store binaries to the repo: local disk or Neon S3."
---
# Artifact Ingest

Store a binary (video, image, PDF, any file) tied to the content pool, under a `{year}/{filename}`
layout. Two contexts, same `artifact` table shape:

- **local** — the SQLite repo + local disk under `{ARTIFACT_ROOT}/{year}/` (default `/data/artifacts`).
- **neon / remote** — the `permathink` Postgres repo + Neon S3-compatible object storage bucket
  `artifacts` on branch `br-late-lake-b4retoc5`, object key `{year}/{filename}` via presigned upload.

## Data model — `artifact`
Same shape both backends (canonical DDL: `references/schema-artifact.sql`):
`id` (TEXT uuid4 hex PK) · `content_id` (TIE to content pool, logical, no hard FK) · `storage_kind`
(`local`|`s3`) · `object_key` (`{year}/{file}`) · `bucket` · `region` · `path_full` (local abs path) ·
`path_filename` · `mime_type` · `byte_size` · `crc32` · `sha256` · `dt_utc` (BIGINT unix epoch).
`object_key` is the primary locator in both modes.

## Year-as-parent-folder rule
`object_key` (and the local on-disk directory) is always `{year}/{filename}`, e.g. `2026/some-new-file.pdf`.
Year defaults to the current UTC year; override with `--year`.

## Filename rule (preserve + unique suffix on collision)
Preserve the ORIGINAL filename (stored in `path_filename`); the object key is `{year}/{original}`. Only when
that key already exists does the script append a unique suffix BEFORE the extension:
`{stem}_{YYYYMMDD-HHMMSS}{ext}`, e.g. `2026/report_20261018-185607.pdf`.
- local: collision is auto-detected (filesystem + SQLite `artifact` table) — no action needed.
- neon: the presigned URL pins the key, so the AGENT must resolve collisions BEFORE presigning: query
  `permathink.artifact` for prefix `'{year}/'` (and/or `list_storage_objects` on the bucket), pick the final
  key, then presign THAT key and pass it to the script via `--object-key` so it matches the URL exactly.

## Running it
`scripts/artifact_ingest.py --mode local|neon --file <path> [options]`

- `--mode local` — copies the file to `{artifact-root}/{year}/`, hashes it, records in the SQLite `artifact`.
- `--mode neon` — REQUIRES `--presigned-url`; PUTs the bytes to that presigned URL, then records
  content + artifact in `permathink`. Obtain the URL from Neon MCP
  `mcp__neon__presign_storage_object(operation=upload, bucket_name=artifacts, object_key={year}/{file},
  content_type=<mime>)`.
- `--content <id>` attaches to an EXISTING content row; otherwise a content row is created (title defaults
  to filename; pass `--title` / `--body` / `--tag` metadata).
- `--filename`, `--year`, `--mime`, `--bucket` (default `artifacts`), `--region` (default `us-east-2`).

Verify read-back counts after commit (the script prints them).

## Agent procedure
1. **Remote:** call `mcp__neon__presign_storage_object` for `{year}/{filename}` to get the upload URL.
2. Run `scripts/artifact_ingest.py` with the mode + metadata (DSN read from
   `/data/cache/scratch/.pgdsn_permathink`; local repo `/data/navajowhite-zebra-617128.sqlite`).
3. Confirm the printed `object_key` / size / sha256 and that a row landed.

## Prereqs
- `neon` mode needs `psycopg` — use the venv `/data/cache/scratch/migvenv/bin/python`.
- `local` mode uses stdlib `sqlite3`.

## Pitfalls
- Neon object storage requires a presigned URL obtained via the MCP tool; the standalone script cannot
  mint one itself (no S3 creds). Always pass `--presigned-url` for `neon`.
- `object_key` must use the year to satisfy the `{year}/...` folder convention.
- Keep the canonical `permathink` Postgres repo as the live store; the local SQLite repo is the disk-only
  context.