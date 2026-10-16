# Proposed: two-level proper-noun metadata engine

**Status:** APPLIED + retrofitted to the live DB (`/data/navajowhite-zebra-617128.sqlite`) on Oct 8 2026.
One-time retroactive tag of existing content: 73 canonical entities, 70 content_entity instances
across 26 content items. DDL reference: `metadata-engine.sql`. Keep tagging entities on new content.

## Purpose

Tag proper nouns (e.g. country Spain, city Durham/NC, person Victor Hugo) at two levels so each
mention is tied to its content while real-world duplicates resolve to one canonical entity.

## Level 1 — content-bound surface instances (`content_entity`)

- One row per proper-noun mention/instance in a given content item; own unique UUID.
- Records only the **surface string** (as tagged), the `content_id` it came from, optional
  `char_start`/`char_end` offsets. `name` is dumb/faithful — no interpretation.
- Identity rule: an instance is scoped to one `content.id`; the same proper noun in two different
  documents is two rows.

## Level 2 — canonical registry (`entity`)

- One row per unique real-world thing; master list, deduplicated, curated.
- Fields: id (UUID), canonical `name`, `entity_type`, `description`, `aliases` (JSON), `properties`
  (JSON), `origin_content_id` (provenance of first discovery), `dt_utc`.

### entity_type — closed but deliberately slow-growing ENUM

Locked set: `organization`, `person`, `location`, `event-single`, `event-recur`, `product`, `service`.

- **Growth rule:** allow additions to grow *very slowly*; target < 10 values at full maturity. Add a
  value only when existing instances genuinely can't be typed by the current set, and each addition
  is reviewed (same governance as `meta_tag_standard`).
- **Subtype rule:** fine distinctions (city vs. country vs. place; a product vs. a service) live in
  `properties` JSON, NOT as new enum values.
  - `location` covers city/country/place — geo detail in `properties` (e.g. `{country, state, city, lat, long}`).
  - `event-single` = one-time occurrence; `event-recur` = recurring series (e.g. Nikon's *annual* photo contest).
  - `product` = a discrete purchasable item (e.g. Store Front Tee); `service` = an ongoing offering
    (e.g. a managed hosting / migration engagement).
- `entity_type` lives on the **canonical** entity; instances inherit it via the bridge FK.

## The bridge

```
content --< content_entity >-- entity
content_entity.entity_id -> entity.id   (many instances -> one canonical entity)
```
- Dedup for free: a new mention resolves to an existing canonical entity and just points at it; a
  not-yet-registered one mints a new canonical entity (via NER/LLM or manual).
- Optional provenance: `entity.origin_content_id` records where the entity was first discovered
  (satisfies the requirement that the unifying layer refers back to the content level).

## Worked example

Content = "Victor Hugo visited Durham, NC in 1843 while Austria pressed Spain\u2026"
- L1 mints instances: (Victor Hugo, person), (Durham, NC, location), (Spain, location).
- L2: Durham-NC resolves to existing entity if present; otherwise a new canonical entity is minted
  and the instance's `entity_id` links to it.

## Key design decisions (agreed)

1. **Entity typing** — closed enum above; grows very slowly (<10).
2. **Instance creation** — LLM/NER extraction with a confidence gate (reuse ~90% policy), or manual.
3. **Resolution** — aliases + disambiguator decide new-mention == existing-entity vs. new entity.
4. **Immutable L1, mutable L2** — instances capture what content said; canonical is where you correct/enrich.
5. **Orthogonal to `meta_tag`** — `meta_tag` is topical/categorical; this engine is entity/graph.
   Both are kept; they answer different questions.

## Open items (before future build-out)

- Entity-resolution strategy exact mechanics (aliases stored; disambiguation logic pending).
- Ongoing ML/NER pipeline + confidence thresholds for auto-tagging new content.
- Note: DDL to the live repo is APPLIED (initial retrospective pass complete).

## Payoffs for current work

- Outbound application system: join to answer "which content references company X / city Y / person Z".
- ColdFusion prospect list: org entities unify Brands Cycle, Bridal Web Solutions, etc.; location
  tagging gives territory analysis.
- Consulting deliverables: entity-typed enrichment from AI-assisted migration research.

## Files

- Design record: this file.
- Proposed DDL: `metadata-engine.sql`.
