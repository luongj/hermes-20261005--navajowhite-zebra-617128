#!/usr/bin/env python3
"""Insert one content item (with tags) into the permathink content repository (Postgres).

Parameterized/transactional — the token-efficient write path for a single forwarded link.

Usage:
  ingest_to_permathink.py <content_title> <content_body> \\
      --source_type <channel> --ingestion_body <desc> \\
      [--tag <tag> [--tag <tag> ...]] \\
      [--entity '<name>|<type>|<description>' [--entity ...]] \\
      [--dsn <file-or-url>]

DSN resolution: --dsn argument -> $PGDSN env -> /data/cache/scratch/.pgdsn_permathink.
Prints Postgres row counts for the item's tables after commit (read-back verification).
"""
import argparse, os, sys, time, uuid
import psycopg

SRC_DEFAULT = "/data/cache/scratch/.pgdsn_permathink"
VALID_TYPES = {"organization","person","location","event-single","event-recur","product","service"}


def resolve_dsn(arg):
    if arg:
        return open(arg).read().strip() if os.path.exists(arg) else arg
    if os.environ.get("PGDSN"):
        return os.environ["PGDSN"]
    return open(SRC_DEFAULT).read().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("body")
    ap.add_argument("--source_type", default="Telegram")
    ap.add_argument("--ingestion_body", required=True)
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--entity", action="append", default=[])
    ap.add_argument("--dsn", default=None)
    a = ap.parse_args()

    dsn = resolve_dsn(a.dsn)
    now = int(time.time())
    ing = uuid.uuid4().hex
    cid = uuid.uuid4().hex

    with psycopg.connect(dsn, connect_timeout=30) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ingest (id,source_type,source_header,ingestion_body,dt_utc) VALUES (%s,%s,%s,%s,%s)",
            (ing, a.source_type, "Forwarded link", a.ingestion_body, now))
        cur.execute(
            "INSERT INTO content (id,ingestion_id,content_title,content_body,dt_utc) VALUES (%s,%s,%s,%s,%s)",
            (cid, ing, a.title, a.body, now))
        n_tags = 0
        for t in a.tag:
            cur.execute("INSERT INTO meta_tag (content_id,tag) VALUES (%s,%s)", (cid, t))
            n_tags += 1
        n_ent = 0
        for spec in a.entity:
            name, typ, desc = (spec.split("|", 2) + ["", ""])[:3]
            eid = uuid.uuid4().hex
            if typ not in VALID_TYPES:
                raise SystemExit(f"invalid entity_type '{typ}' (valid: {sorted(VALID_TYPES)})")
            cur.execute(
                "INSERT INTO entity (id,name,entity_type,description,aliases,properties,origin_content_id,dt_utc) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (eid, name, typ, desc, None, None, cid, now))
            cur.execute(
                "INSERT INTO content_entity (id,content_id,name,char_start,char_end,entity_id,dt_utc) "
                "VALUES (%s,%s,%s,NULL,NULL,%s,%s)",
                (uuid.uuid4().hex, cid, name, eid, now))
            n_ent += 1
        con.commit()
        # read-back verification
        cur.execute("SELECT COUNT(*) FROM content WHERE id=%s", (cid,))
        c_chk = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM meta_tag WHERE content_id=%s", (cid,))
        t_chk = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM content_entity WHERE content_id=%s", (cid,))
        e_chk = cur.fetchone()[0]
    print("ingested", cid)
    print("content rows:", c_chk, "| meta_tag rows:", t_chk, "/", n_tags, "| content_entity rows:", e_chk, "/", n_ent)
    return 0 if (c_chk == 1 and t_chk == n_tags and e_chk == n_ent) else 1


if __name__ == "__main__":
    sys.exit(main())
