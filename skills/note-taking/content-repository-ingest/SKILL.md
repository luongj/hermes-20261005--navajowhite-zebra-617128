---
name: content-repository-ingest
description: Log forwarded jobs/links into the content repository DB.
---
# Content Repository Ingest

Store a forwarded job listing, link, URL, or screen capture into the content repository
(referenced by SOUL.md as `core_database`). Store only — do not launch into analysis unless the user asks.
Confirm tersely (what was stored + its tags); do not analyze, editorialize, or add commentary to any
item (links, anecdotes, images alike) unless asked.

## The repository
- Postgres `permathink` on Neon (project `hermes-edwards`, default branch `production`). Deployed 2026-10-15.
- Write via `scripts/ingest_to_permathink.py` (parameterized; reads DSN from `/data/cache/scratch/.pgdsn_permathink`
  or `PGDSN` env), or the Neon MCP (`mcp__neon__run_sql[_transaction]`) on database `permathink`.
- The former SQLite file (`/data/navajowhite-zebra-617128.sqlite`) is retained as a read-only archive — not the live store.

## Schema (Postgres `permathink`; canonical DDL in `references/schema.sql`)
- `ingest` (id TEXT PK uuid4-hex, source_type, source_header, ingestion_body, dt_utc BIGINT epoch)
- `content` (id TEXT PK uuid4-hex, ingestion_id, content_title, content_body, dt_utc BIGINT)
- `meta_tag` (content_id, tag) — tag validated by `CHECK (tag ~ '^[a-z0-9_-]+$')`.
- `meta_tag_standard` (id TEXT PK uuid4-hex, meta_tag TEXT UNIQUE, description, dt_utc BIGINT)
  — the canonical allowed tag set. Only these keys may be used as tags.
- `artifact` (id TEXT PK, host_ip, path_full, path_filename, CRC32, dt_utc BIGINT) — attached files.
- `entity` (id TEXT PK, name, entity_type CHECK (7 values), description, aliases JSONB, properties JSONB,
  origin_content_id, dt_utc) — canonical proper-noun registry (Level 2).
- `content_entity` (id TEXT PK, content_id, name, char_start, char_end, entity_id, dt_utc,
  UNIQUE(content_id,name,char_start,char_end)) — surface instances (Level 1).
- **No FOREIGN KEY constraints** (referential integrity is application-managed). UNIQUE/CHECK constraints
  and indexes ARE enforced.

Canonical tags: `ai-inference`, `ai-society`, `architecture`, `buy-apparel`, `non-retail`,
`travel`, `open-source`, `tech`, `tech-infra`, `business`, `economics`, `humor`,
`sustainability`, `family`, `job-listing`, `job-consult-prospect`, `prospect-coldfusion`,
`watchlist`, `buy-tech`, `buy`, `untagged`. Use `watchlist` for books/TV/movies the operator intends to
watch, `buy-tech` for technology products considered for purchase, `buy` for miscellaneous items
considered for purchase, `job-listing` for job postings, `job-consult-prospect` for pre-sales/consulting
leads, `buy-apparel` for apparel/merch items considered for purchase, `prospect-coldfusion` for
prospects/leads running ColdFusion (.cfm), `architecture` for built-environment design,
`non-retail` for maker/secondary-marketplace transactions, `ai-inference` for model
serving/running and inference costs, `ai-society` for AI's societal/workplace impact,
`tech-infra` for cloud/hosting/deployment infrastructure, `untagged` when no tag appropriately
matches.

Note (context, not a rule): `prospect-coldfusion` tags .cfm/ColdFusion sites as leads for the
user's AI-driven ColdFusion migration/maintenance consulting engagements — record the page, its
CF surface (cart/login/index pages), and any migration-relevant signals.

Binaries (video/image/PDF) that accompany or are forwarded for storage use the `artifact-ingest`
skill (local disk + SQLite, or Neon S3 + permathink) and tie to this same content pool.

Ids are `uuid4().hex` (32-char, no dashes) stored as TEXT — a Postgres `uuid` type would reject them.
`dt_utc` is a BIGINT unix epoch (not timestamptz) for exact round-trips.

## Tagging policy
Apply tags from `meta_tag_standard` only (DB enforces this). Rules:
1. **Assign a tag only when ~90% confident** it fits the content. Below that confidence, do not
   add it.
2. **Up to 2 tags per item automatically** — no adjustment needed.
3. **3 or more plausible tags → prompt the user** to confirm/trim the set; do not auto-assign
   the whole set.
4. **No tag appropriately matches → tag `untagged`** (never leave an item without a tag).

## Ingest procedure
1. Insert into `ingest`, `content`, and `meta_tag` in Postgres `permathink` — use
   `scripts/ingest_to_permathink.py` (parameterized, token-efficient) or the Neon MCP
   (`mcp__neon__run_sql_transaction`, database `permathink`). `source_type`: the channel (Telegram, WhatsApp, email).
2. `ingestion_body`: describe the forwarded link (the URL, and why/logged-source), not the page chrome.
3. Clean the actual content into `content.content_body` as readable markdown; keep `content_title` concise.
4. Apply `meta_tag`s per the Tagging policy below (several rows per content). The DB enforces the charset
   CHECK on `tag` (a non-standard tag is rejected); FK integrity is application-managed.
5. Migrate pre-standard tags when upgrading: `job search` → `job-listing`.
6. Verify after commit: count rows back from each affected table (read-back, not assumption).

## Pitfalls
- De-duplicate forwarded URLs that are the same page — fragment/anchor or UTM variants (e.g.
  `westie.fyi/?ch=x` vs `westie.fyi/?ch=x#cities`) — store the canonical once and note the variant.
- At the end of an ingestion session, do NOT give a total recap (counts/summary) unless asked — just
  confirm each item was stored.
- LinkedIn job pages carry ~32k chars of chrome/nav; extract the clean listing and store that, not raw HTML.
- Tag keys map to `meta_tag_standard`, not the free-form SOUL.md interest list.
- There are NO foreign keys in `permathink` — referential integrity is application-managed. Only the
  charset CHECK on `meta_tag.tag` and the `entity.entity_type` CHECK are DB-level guarantees.
- `id` columns are TEXT (uuid4 hex, no dashes); `dt_utc` is BIGINT unix epoch — do not cast to uuid/timestamptz.
- `entity.aliases`/`properties` are JSONB — pass valid JSON or NULL.
- Repo scripts that write Postgres need `psycopg` — run them with `/data/cache/scratch/migvenv/bin/python`,
  not the system `python3` (no psycopg); a `neon`-mode run fails at `import psycopg` before any upload.
- `entity.name` is NOT unique and the ingest script mints a new id per `--entity` — resolve existing
  canonical entities by name (`SELECT id FROM entity WHERE name=...`) and reuse the id instead of
  re-minting, or duplicate canonical entities accumulate.
- Bulk loads (migration, backfill, many rows): use the parameterized `ingest_to_permathink.py`
  (psycopg) rather than pasting INSERT literals through the Neon MCP — the data stays out of model
  context (cheap) and you avoid SQL-escaping bugs on content with quotes/newlines/emoji. Reserve MCP
  `run_sql` for small one-row DDL/writes.

## Two-level proper-noun metadata engine (applied)
Live in `permathink`: a content-bound surface-instance layer (`content_entity`) linked via `entity_id` to a
canonical registry (`entity`) with a slow-growing closed enum
`organization / person / location / event-single / event-recur / product / service`.
(No database FK — the join is logical, application-managed.) Design record:
`references/metadata-engine.md`; DDL: `references/schema.sql`.
Retroactive tag of pre-existing content is done (carried into permathink 2026-10-15). Keep tagging entities
on every new ingest: look up the entity by NAME first and reuse the existing canonical id; only mint a new
`entity` row when the name is genuinely new. There is no `UNIQUE(name)` in permathink — dedupe in the
ingest step (`SELECT id FROM entity WHERE name=...`), not via a DB constraint.
