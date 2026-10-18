-- artifact table — shared logical shape; applies to BOTH backends.
-- Ids: uuid4().hex TEXT. dt_utc: unix epoch (BIGINT in PG, INTEGER in SQLite).
-- storage_kind: 'local' (disk + SQLite repo) | 's3' (Neon object storage + Postgres repo).
-- object_key = '{year}/{filename}' (year is a parent folder — see convention below).
-- content_id ties the binary to the content pool (logical ref; NO hard FK per content-repo design).
-- object_key is the primary locator in both modes; path_full is the local absolute path (local mode).

-- *** Postgres (permathink) ***
CREATE TABLE IF NOT EXISTS artifact (
  id            TEXT PRIMARY KEY,
  content_id    TEXT,
  storage_kind  TEXT NOT NULL CHECK (storage_kind IN ('local','s3')),
  object_key    TEXT,
  bucket        TEXT,
  region        TEXT,
  path_full     TEXT,
  path_filename TEXT NOT NULL,
  mime_type     TEXT,
  byte_size     BIGINT,
  crc32         TEXT,
  sha256        TEXT,
  dt_utc        BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS artifact_content_idx ON artifact(content_id);
CREATE INDEX IF NOT EXISTS artifact_key_idx ON artifact(object_key);

-- *** SQLite (local repo) ***
CREATE TABLE IF NOT EXISTS artifact (
  id            TEXT PRIMARY KEY,
  content_id    TEXT,
  storage_kind  TEXT NOT NULL CHECK (storage_kind IN ('local','s3')),
  object_key    TEXT,
  bucket        TEXT,
  region        TEXT,
  path_full     TEXT,
  path_filename TEXT NOT NULL,
  mime_type     TEXT,
  byte_size     INTEGER,
  crc32         TEXT,
  sha256        TEXT,
  dt_utc        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifact_content ON artifact(content_id);
CREATE INDEX IF NOT EXISTS idx_artifact_key ON artifact(object_key);

-- Year-as-parent-folder convention:
--   object_key / local dir == '{year}/{filename}', e.g. 2026/some-new-file.pdf
--   Local disk root default: /data/artifacts/{year}/

-- Neon S3-compatible object storage (branch br-late-lake-b4retoc5):
--   s3_endpoint = https://br-late-lake-b4retoc5.storage.c-6.us-east-2.aws.neon.tech
--   region = us-east-2 (force path style)
--   bucket = artifacts (private), created 2026-10-18.
--   Upload = presign_storage_object(operation=upload, bucket_name=artifacts, object_key='{year}/{file}')
--            -> PUT bytes to the returned URL (no S3 credentials needed).
