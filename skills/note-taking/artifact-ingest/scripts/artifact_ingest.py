#!/usr/bin/env python3
"""Store a binary into the content repository artifact pool.

Modes:
  local: copy to {ARTIFACT_ROOT}/{year}/ on disk + record in the SQLite repo.
  neon:  PUT bytes to a Neon S3 presigned URL + record in permathink (Postgres).

Naming (both modes): preserve the ORIGINAL filename, keyed as '{year}/{filename}'. Only when that key
already exists (collision) append a unique suffix BEFORE the extension, e.g.
  'report_20261018-185607.pdf'  (still under its {year}/ folder).
  local: collision is detected against the filesystem + the SQLite artifact table.
  neon:  the object_key is pinned by the presigned URL the agent mints, so the AGENT resolves any
         collision first (query permathink artifact for prefix '{year}/'), presigns the FINAL key, and
         passes it via --object-key (which must match that URL exactly).

Attaches to an existing content row when --content <id> is given; else creates one.
"""
import argparse, hashlib, os, shutil, sqlite3, subprocess, sys, time, uuid, zlib

DEFAULT_LOCAL_REPO  = "/data/navajowhite-zebra-617128.sqlite"
DEFAULT_PG_DSN_FILE = "/data/cache/scratch/.pgdsn_permathink"
DEFAULT_ARTIFACT_ROOT = "/data/artifacts"

MIME = {
    ".pdf":"application/pdf",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",
    ".gif":"image/gif",".webp":"image/webp",".mp4":"video/mp4",".mov":"video/quicktime",
    ".webm":"video/webm",".mp3":"audio/mpeg",".m4a":"audio/mp4",".wav":"audio/wav",
    ".txt":"text/plain",".md":"text/markdown",".zip":"application/zip",
    ".json":"application/json",".csv":"text/csv",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",".pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

def sha256(path, chunk=1<<20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def crc32(path, chunk=1<<20):
    c = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            c = zlib.crc32(b, c)
    return format(c & 0xFFFFFFFF, "08x")

def mime_of(name, forced):
    if forced: return forced
    return MIME.get(os.path.splitext(name)[1].lower(), "application/octet-stream")

def ts_suffix(t=None):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t if t is not None else time.time()))

def local_key_exists(artifact_root, key, cur):
    if os.path.exists(os.path.join(artifact_root, key)):
        return True
    try:
        return cur.execute("SELECT 1 FROM artifact WHERE object_key=?", (key,)).fetchone() is not None
    except Exception:
        return False

def pick_local_key(artifact_root, year, basename, cur):
    """Original filename first; add _YYYYMMDD-HHMMSS suffix only on collision."""
    if not local_key_exists(artifact_root, f"{year}/{basename}", cur):
        return f"{year}/{basename}"
    stem, ext = os.path.splitext(basename)
    ts = ts_suffix()
    i = 0
    while True:
        name = f"{stem}_{ts}{ext}" if i == 0 else f"{stem}_{ts}_{i}{ext}"
        key = f"{year}/{name}"
        if not local_key_exists(artifact_root, key, cur):
            return key
        i += 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["local", "neon"])
    ap.add_argument("--file", required=True, help="path to the binary to store")
    ap.add_argument("--filename", default=None, help="original filename (defaults to source basename)")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--object-key", default=None, help="neon only: final object key (must match the presigned URL)")
    ap.add_argument("--content", default=None, help="existing content_id to attach to")
    ap.add_argument("--title", default=None)
    ap.add_argument("--body", default="")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--mime", default=None)
    ap.add_argument("--presigned-url", default=None, help="neon only: presigned upload URL from Neon MCP")
    ap.add_argument("--bucket", default="artifacts")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT)
    a = ap.parse_args()

    local_repo  = os.environ.get("LOCAL_REPO", DEFAULT_LOCAL_REPO)
    pg_dsn_file = os.environ.get("PG_DSN_FILE", DEFAULT_PG_DSN_FILE)

    if not os.path.isfile(a.file):
        sys.exit(f"source file not found: {a.file}")
    basename = a.filename or os.path.basename(a.file)
    year = a.year if a.year else int(time.strftime("%Y", time.gmtime()))
    mime = mime_of(basename, a.mime)
    size = os.path.getsize(a.file)
    s256 = sha256(a.file)
    c32  = crc32(a.file)
    now = int(time.time())
    content_id = a.content

    if a.mode == "local":
        con = sqlite3.connect(local_repo); con.execute("PRAGMA foreign_keys=ON"); cur = con.cursor()
        try:
            object_key = pick_local_key(a.artifact_root, year, basename, cur)
            dest = os.path.join(a.artifact_root, object_key)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(a.file, dest)
            if not content_id:
                cid = uuid.uuid4().hex
                cur.execute("INSERT INTO content (id,ingestion_id,content_title,content_body,dt_utc) VALUES (?,?,?,?,?)",
                            (cid, None, a.title or basename, a.body, now))
                for t in a.tag:
                    cur.execute("INSERT INTO meta_tag (content_id,tag) VALUES (?,?)", (cid, t))
                content_id = cid
            aid = uuid.uuid4().hex
            cur.execute("""INSERT INTO artifact (id,content_id,storage_kind,object_key,bucket,region,path_full,path_filename,mime_type,byte_size,crc32,sha256,dt_utc)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (aid, content_id, "local", object_key, None, None, dest, basename, mime, size, c32, s256, now))
            con.commit()
            r = cur.execute("SELECT object_key,byte_size,sha256 FROM artifact WHERE id=?", (aid,)).fetchone()
            print(f"LOCAL stored -> {dest}")
            print(f"object_key={r[0]} filename={basename} size={r[1]} sha256={r[2][:16]}... content_id={content_id}")
        finally:
            con.close()
    else:  # neon
        if not a.presigned_url:
            sys.exit("neon mode requires --presigned-url (from Neon MCP presign_storage_object)")
        object_key = a.object_key or f"{year}/{basename}"
        import psycopg
        cp = subprocess.run(["curl","-s","-o","/dev/null","-w","%{http_code}",
                             "-X","PUT","--upload-file",a.file,
                             "-H",f"Content-Type: {mime}", a.presigned_url], capture_output=True, text=True)
        code = cp.stdout.strip()
        if code not in ("200", "201"):
            sys.exit(f"presigned upload failed (HTTP {code}): {cp.stderr[:200]}")
        dsn = open(pg_dsn_file).read().strip()
        with psycopg.connect(dsn) as con:
            with con.cursor() as cur:
                if not content_id:
                    cid = uuid.uuid4().hex
                    cur.execute("INSERT INTO content (id,ingestion_id,content_title,content_body,dt_utc) VALUES (%s,%s,%s,%s,%s)",
                                (cid, None, a.title or basename, a.body, now))
                    for t in a.tag:
                        cur.execute("INSERT INTO meta_tag (content_id,tag) VALUES (%s,%s)", (cid, t))
                    content_id = cid
                aid = uuid.uuid4().hex
                cur.execute("""INSERT INTO artifact (id,content_id,storage_kind,object_key,bucket,region,path_full,path_filename,mime_type,byte_size,crc32,sha256,dt_utc)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (aid, content_id, "s3", object_key, a.bucket, a.region, None, basename, mime, size, c32, s256, now))
                con.commit()
                r = cur.execute("SELECT object_key,byte_size,sha256,bucket FROM artifact WHERE id=%s", (aid,)).fetchone()
                print(f"NEON stored -> s3://{r[3]}/{r[0]}")
                print(f"filename={basename} size={r[1]} sha256={r[2][:16]}... content_id={content_id}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
