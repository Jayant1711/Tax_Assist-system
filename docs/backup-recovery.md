# Backup & Recovery

> Sprint 3 Wave F (2026-11-01). Covers the SQLite store (`TAX_DB_PATH`), the append-only JSONL streams (audit / blackbox / app log), the retention interplay, and the recovery runbook. Tool: `backend/tools/backup_db.py` (pure stdlib). Deployment context: [deployment.md](deployment.md) §4/§12.

## 1. What state exists

| Artifact | Container path (volume) | Content | Loss impact |
|---|---|---|---|
| SQLite store | `/app/data/taxassist.db` (`db-data`) | `users`, `auth_sessions`, `app_sessions` (ADR-012/013) | Accounts + conversation state gone; users must re-register; audit stream still names session ids |
| Audit stream | `/app/logs/audit/session_audit.jsonl` + rotations `.N` (`logs-data`) | PII-minimized interaction + auth event records | Compliance trail lost |
| Blackbox streams | `/app/logs/blackbox/<sid>.jsonl` (`logs-data`) | Per-session turn records | Regression-audit corpus lost |
| App log | `/app/logs/app/app.jsonl` + rotations (Wave H) | Structured operational log | Operational forensics lost |

All four live in the two named volumes (`db-data`, `logs-data`) created by docker-compose. `docker compose down` preserves them; `docker compose down -v` deletes them — that is the disaster being protected against, along with host-disk failure and store corruption.

## 2. SQLite backup procedure

Hot backup (preferred — the app keeps serving; one worker + WAL makes the online snapshot consistent):

```bash
cd backend
python tools/backup_db.py --out-dir /backups
# -> {"timestamp": "...", "database_backup": "/backups/taxassist.<UTC-timestamp>.bak",
#     "database_backup_bytes": 45056, "streams": {"audit/session_audit.jsonl": ["..."], ...}}
```

- `backup_database` uses the sqlite3 **online backup API** (the `.backup` command's library form; `VACUUM INTO` would be an equivalent single-file alternative). The copy is written as `.bak.tmp`, verified with `PRAGMA integrity_check`, then atomically renamed — a failed run never leaves a plausible-looking corrupt `.bak`.
- Frequency: nightly is the baseline; add a pre-deploy backup before every `docker compose down`/migration/version upgrade.
- Store backups OUTSIDE the volumes (another disk, object storage). `cp` of a live WAL database is NOT a backup — always use the tool (or `sqlite3 ".backup"`).
- Bare-metal equivalent: `sqlite3 data/taxassist.db "VACUUM INTO '/backups/taxassist.bak'"` while the app is stopped or with the same one-writer discipline.

## 3. JSONL stream copies (rotation-aware)

The streams rotate: the active file shifts to `.1` and older generations up (`TAX_AUDIT_MAX_FILES` kept). **Concatenating `.max … .2 .1` then the active file replays every line in write order** — copying only the active file silently loses the older generations.

```bash
python tools/backup_db.py --skip-db --out-dir /backups
# copies, per stream family (audit/, blackbox/, app/):
#   session_audit.jsonl.5 ... session_audit.jsonl.1   (oldest generation first)
#   session_audit.jsonl                               (active stream last)
```

`copy_jsonl_streams` preserves the `audit/`, `blackbox/`, `app/` layout so a restored tree is byte-for-byte what the app expects. Verify a copy before trusting it:

```bash
python -c "from tools.backup_db import scan_jsonl_integrity; print(scan_jsonl_integrity('/backups/audit/session_audit.jsonl'))"
# {"total_lines": 221, "corrupt_lines": 0, "valid_lines": 221}
```

A corrupt-line count > 0 in a BACKUP copy means the live stream had a damaged tail — preserve the copy as-is (append-only discipline: never "fix" lines) and investigate the live stream separately.

## 4. Retention interplay

- `TAX_AUDIT_RETENTION_DAYS` (default 30) and `TAX_APP_LOG_RETENTION_DAYS` sweep only **rotated generations of the LIVE streams**, by mtime. The active file is never deleted by the app.
- Backups are the archive: nothing in the app touches them, and retention settings do not prune `/backups`. Apply your own retention/compliance window to the backup directory (DPDP Act 2023: keep the minimum you have a lawful basis for — the audit stream is PII-minimized by default, `TAX_AUDIT_STORE_TEXT` off).
- Practical consequence: with 30-day live retention and nightly backups, the recoverable history is "last 30 days live + every nightly since backups began". Raising `TAX_AUDIT_RETENTION_DAYS` does NOT resurrect already-swept generations.

## 5. Recovery runbook (store corruption / data loss / bad deploy)

1. **Stop**: `docker compose stop backend` (frontend may stay up; it will surface errors). No writer touches the store during recovery.
2. **Snapshot the failure first** (if disk space allows): copy the damaged `db-data` contents and `logs-data` aside — post-mortems and DPDP incident records need the evidence.
3. **Restore the DB**: copy the chosen `taxassist.<ts>.bak` over `/app/data/taxassist.db` inside the `db-data` volume (e.g. `docker compose run --rm -v db-data:/data alpine cp ...` or a bind-mounted helper container). **Delete any stale `taxassist.db-wal` / `taxassist.db-shm` from the dead instance first** — replaying an old WAL over a restored file corrupts it.
4. **Restore the log streams**: copy the backed-up `audit/`, `blackbox/`, `app/` trees back into `/app/logs` (volume `logs-data`), preserving generation names. Keep the active-file/generation layout exactly as copied (`.N` files are just files; the app re-discovers them by name).
5. **Start**: `docker compose start backend` (or `up -d`), wait for `healthy`.
6. **Verify**: `curl http://127.0.0.1:8000/health` → `200 {"status":"ok","checks":{"db":"ok","audit":"ok"},...}`. Then a functional smoke: register/login, `POST /sessions`, one `/chat` turn.
7. **Stream integrity line-scan**: run `scan_jsonl_integrity` over every restored stream; record the corrupt-line counts in the incident record. Sessions whose ids appear in the restored audit stream but whose `app_sessions` rows predate the backup are gone — tell affected users honestly (their conversation state cannot be recovered from the audit stream, which is PII-minimized by design).
8. **Incident record in the audit**: append one structured event to the audit stream documenting the recovery (what failed, what was restored from which backup, verification result). Use the same append-only discipline — e.g. a small Python snippet calling `audit_logger.append_jsonl_line` with `{"timestamp": ..., "session_id": "ops-incident-<ts>", "event": "recovery_restore", ...}` — never edit existing lines.
9. **Post-mortem**: check `/auth/login` lockout counters were reset by the restore (old `failed_logins` values came back with the backup — expected), rotate any credentials users shared with support, and review whether the backup cadence needs tightening.

## 6. What is NOT covered

- Forward replication / zero-RPO: none. The documented deployment accepts a recovery point of "last backup".
- Cross-host migration: stop the stack, back up, ship the `.bak` + stream copies, restore at the destination (steps 3–6). The store is portable plain SQLite.
- Password recovery: scrypt hashes only (ADR-012) — a restored DB restores hashes, not plaintexts; password resets go through re-registration or a future admin flow.
