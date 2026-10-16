-- Proposed two-level proper-noun metadata engine.
-- STATUS: PROPOSED ONLY. NOT applied to /data/navajowhite-zebra-617128.sqlite.
-- Design record: references/metadata-engine.md
-- Requires the `content` table (already present in the content repo) and
-- `PRAGMA foreign_keys=ON;` per connection.

-- Level 2 first (Level 1 references it via the bridge FK).
CREATE TABLE IF NOT EXISTS entity (
  id               TEXT PRIMARY KEY,              -- uuid4 hex, canonical id
  name             TEXT NOT NULL,                 -- canonical (disambiguated) name
  entity_type      TEXT NOT NULL,                 -- closed-but-growable enum (see CHECK)
  description      TEXT,
  aliases          TEXT,                          -- JSON array of alternate spellings
  properties       TEXT,                          -- JSON: geo, dates, industry, etc.
  origin_content_id TEXT,                         -- provenance: FK content.id where first discovered
  dt_utc           INTEGER NOT NULL,              -- epoch seconds
  CHECK (entity_type IN (
    'organization','person','location',
    'event-single','event-recur','product','service'
  ))
);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(entity_type);

-- Level 1: content-bound surface instances.
CREATE TABLE IF NOT EXISTS content_entity (
  id          TEXT PRIMARY KEY,                  -- uuid4 hex, unique per instance
  content_id  TEXT NOT NULL REFERENCES content(id),
  name        TEXT NOT NULL,                     -- surface string exactly as tagged
  char_start  INTEGER,                           -- optional start offset in content
  char_end    INTEGER,                           -- optional end offset
  entity_id   TEXT REFERENCES entity(id),        -- THE BRIDGE -> canonical entity
  dt_utc      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_content_entity_content ON content_entity(content_id);
CREATE INDEX IF NOT EXISTS idx_content_entity_entity ON content_entity(entity_id);

-- Dedup: one instance per (content, surface string, offsets).
CREATE UNIQUE INDEX IF NOT EXISTS uq_content_entity
  ON content_entity(content_id, name, char_start, char_end);

-- Growth governance: adding a value to the entity_type CHECK is the ONLY allowed way to
-- extend the enum, and it must be reviewed + documented. Target < 10 values at maturity.
-- Subtype detail belongs in entity.properties, not in new enum values.
