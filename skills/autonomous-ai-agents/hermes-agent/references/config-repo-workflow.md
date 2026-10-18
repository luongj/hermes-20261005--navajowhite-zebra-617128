# Version-controlling Hermes config in a git repo

Keep the live Hermes configuration under version control so changes are reviewable and recoverable.
Pattern used for this user: a dedicated GitHub repo holding `SOUL.md`, `config.yaml`, and `skills/`.

## Layout
- Working tree is a **live clone** on the box (e.g. `/data/hermes-cfg`), clones the config GitHub repo.
- Source of truth stays `/data/` (SOUL.md, config.yaml, skills/); the repo is a synced mirror.
- Git identity must be set for the commits (name + email).

## Sync-and-push procedure
1. Copy live files into the working tree:
   `cp /data/SOUL.md /data/config.yaml <repo>/` and `cp -r /data/skills/. <repo>/skills/`.
2. Ensure `.gitignore` excludes secrets before staging: `.env`, `*.env`, `*.sqlite*`, `*.db`, `*.pem`,
   `.pgdsn_*`, `cache/`, `.cache/`, `cron/output/`, `.DS_Store`.
3. **Secret-scan the staged set before committing** (docs legitimately contain redacted examples like
   `ghp_xx...xxxx`; require a realistic secret length, e.g. `ghp_[A-Za-z0-9]{15,}`):
   `git add -A && git grep --cached -nE '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{15,}|npg_[A-Za-z0-9]{15,}|AKIA[A-Z0-9]{12,})'`
   and review any hits — most are placeholder examples, not real credentials.
4. Commit and push. **The push is an irreversible external write — it triggers the approval gate;
   get explicit user consent and expect it to gate.**
5. Verify the remote took the new HEAD: `git fetch -q origin && git rev-parse --short origin/HEAD` == local.

## Credentials
- Push with a **fine-grained PAT** (Contents read/write, scoped to just the config repo, expiring) stored
  as `GITHUB_TOKEN` in the platform env (see `platform-env-injection.md` for reading it) and wired via
  git `credential.helper store` → `~/.git-credentials` (chmod 600).
- Prefer fine-grained PAT for a git-only, one-repo config loop over a classic PAT (global `repo` scope)
  or `gh` OAuth. The hosted GitHub connector is API-level only and does NOT give `git` push/pull creds.

## Recurring review
Standing behaviour for this user: a cron job prompts a config-repo review every 14 days (surface
uncommitted changes, local-vs-origin divergence, disk-vs-repo drift) and asks whether to commit/push —
it must never push autonomously. Keep such review jobs prompt-only.
