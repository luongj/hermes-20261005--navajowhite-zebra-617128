-- Content repository schema — Postgres `permathink` (Neon, project `hermes-edwards`).
-- Migrated 2026-10-15 from the SQLite store (/data/navajowhite-zebra-617128.sqlite — now read-only archive).
-- DESIGN: NO FOREIGN KEY constraints (referential integrity is application-managed).
-- UNIQUE / CHECK constraints and indexes ARE enforced.
-- Ids: TEXT = uuid4().hex (32 chars, no dashes).  dt_utc: BIGINT unix epoch.

CREATE TABLE IF NOT EXISTS ingest (
  id              TEXT PRIMARY KEY,          -- uuid4 hex
  source_type     TEXT,                      -- Telegram / WhatsApp / email
  source_header   TEXT,
  ingestion_body  TEXT,
  dt_utc          BIGINT                     -- epoch seconds
);

CREATE TABLE IF NOT EXISTS content (
  id              TEXT PRIMARY KEY,          -- uuid4 hex
  ingestion_id    TEXT,                      -- (no FK) -> ingest.id
  content_title   TEXT,
  content_body    TEXT,
  dt_utc          BIGINT
);

CREATE TABLE IF NOT EXISTS meta_tag_standard (
  id          TEXT PRIMARY KEY,              -- uuid4 hex
  meta_tag    TEXT UNIQUE,                   -- canonical tag: [a-z0-9_-]
  description TEXT,
  dt_utc      BIGINT
);

CREATE TABLE IF NOT EXISTS meta_tag (
  content_id   TEXT,                         -- (no FK) -> content.id
  tag          TEXT,                         -- (no FK) -> meta_tag_standard.meta_tag
  CHECK (tag ~ '^[a-z0-9_-]+$')              -- charset constraint
);
CREATE INDEX IF NOT EXISTS meta_tag_content_idx ON meta_tag(content_id);
CREATE INDEX IF NOT EXISTS meta_tag_tag_idx   ON meta_tag(tag);

CREATE TABLE IF NOT EXISTS artifact (
  id            TEXT PRIMARY KEY,            -- uuid4 hex
  content_id    TEXT,                        -- ties binary to the content pool (logical; no FK)
  storage_kind  TEXT NOT NULL CHECK (storage_kind IN ('local','s3')),
  object_key    TEXT,                        -- '{year}/{filename}' primary locator
  bucket        TEXT,
  region        TEXT,
  path_full     TEXT,                        -- local absolute path (local mode)
  path_filename TEXT NOT NULL,
  mime_type     TEXT,
  byte_size     BIGINT,
  crc32         TEXT,
  sha256        TEXT,
  dt_utc        BIGINT
);
CREATE INDEX IF NOT EXISTS artifact_content_idx ON artifact(content_id);
CREATE INDEX IF NOT EXISTS artifact_key_idx ON artifact(object_key);
-- Full artifact feature (local disk + Neon S3 upload, SQLite variant, scripts): see `artifact-ingest` skill.

CREATE TABLE IF NOT EXISTS entity (
  id                TEXT PRIMARY KEY,        -- uuid4 hex
  name              TEXT NOT NULL,
  entity_type       TEXT NOT NULL CHECK (entity_type IN
    ('organization','person','location','event-single','event-recur','product','service')),
  description       TEXT,
  aliases           JSONB,
  properties        JSONB,
  origin_content_id TEXT,                    -- (no FK) -> content.id
  dt_utc            BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS entity_type_idx ON entity(entity_type);

CREATE TABLE IF NOT EXISTS content_entity (
  id          TEXT PRIMARY KEY,              -- uuid4 hex
  content_id  TEXT NOT NULL,                 -- (no FK) -> content.id
  name        TEXT NOT NULL,
  char_start  BIGINT,
  char_end    BIGINT,
  entity_id   TEXT,                          -- (no FK) -> entity.id
  dt_utc      BIGINT NOT NULL,
  UNIQUE (content_id, name, char_start, char_end)
);
CREATE INDEX IF NOT EXISTS content_entity_content_idx ON content_entity(content_id);
CREATE INDEX IF NOT EXISTS content_entity_entity_idx  ON content_entity(entity_id);

-- Canonical tag set (19): ai-inference, ai-society, architecture, buy-apparel, non-retail, travel,
-- open-source, tech, tech-infra, business, economics, humor, sustainability, family, job-listing,
-- job-consult-prospect, prospect-coldfusion, watchlist, untagged (seeded in meta_tag_standard).
