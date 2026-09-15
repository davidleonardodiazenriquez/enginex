# PostgreSQL migration to the second tenant

Requested on 2026-09-15. Copy the existing Enginex database to the new server;
leave the Container App's database configuration unchanged for a later switch.

| Setting | Source | Destination |
| --- | --- | --- |
| Host | `psql-test-athon-test-un-001.postgres.database.azure.com` | `enginex-postgresql.postgres.database.azure.com` |
| Database | `enginex` | `enginex` |
| Port | `5432` | `5432` |
| Admin username supplied | `psqladmin` | `psqladmin` — confirmed by user |
| SSL | Required | Required |

## Completed copy and verification

The new password supplied by the user authenticated successfully from the
Container App. Both servers run PostgreSQL 18.6 and use SSL. The destination
database did not exist before this operation.

The source snapshot was taken at **2026-09-15 10:26:16 UTC / 14:26:16 Dubai**.
A native custom-format `pg_dump` used an exported repeatable-read snapshot, and
`pg_restore` restored the new `enginex` database in a single transaction. The
source database was not modified. Database objects are owned by the existing
destination `psqladmin` login; Azure-managed server roles were not recreated.

Verified at 10:32 UTC, with application checks completed afterward:

- All **19 tables** have identical row counts and content hashes.
- All **17 sequences** have identical values and called states.
- The copy contains 2 application users, 6 assets, 733 records, 13 contracts,
  13 completed extraction runs, 372 extracted fields and 1 association event.
- Django user password hashes, permissions, migration history, document storage
  keys, page quotations and review state were preserved with the table contents.
- Schema comparison passed after accounting for native restore normalization:
  dropped columns no longer leave gaps in physical column ordinals, and a known
  partial index renders equivalent array casts differently. Other definitions
  were compared without normalization. The partial index additionally rejected
  duplicate queued/running extractions and allowed completed ones in a rolled
  back probe using explicit IDs, so no sequence values were consumed.
- Deployed Django code rendered 11 authenticated map, dashboard, report, contract
  and AI pages against the destination. No migrations are pending.
- All 13 source PDFs opened through report/record links and matched their stored
  SHA-256 hashes. A PDF page preview also rendered successfully.
- A real EnginexAI request queried the destination and returned a chart covering
  all six locations, with coverage of 733 records, 13 contracts and 372 fields.

The application checks used a temporary signed session for the copied `demo`
account in a read-only verification process. They did not reset passwords, write
sessions to the database or change the serving app's connection.

ACR quick task **`dgy`** performed the dump and restore. Its initial strict schema
comparator exited nonzero on the equivalent representations described above.
The destination was inspected rather than restored again, the comparator was
corrected, and subsequent content/schema/index/application checks passed inside
the Container App. Do not interpret that historical task exit as an incomplete
restore, or claim that the original ACR task itself returned success.

Detailed evidence is in ignored `tmp/database-migration-verified.json` and
`tmp/database-copy-run.log`. The native dump was temporary and was deleted after
the task; no copy of database contents or passwords was added to source control.
`scripts/copy_database.py` documents the guarded procedure and requires native
PostgreSQL client tools plus psycopg2 in the migration environment, not in the app.
It refuses to overwrite an existing destination database.

## Later connection switch

The serving app remains on the original server and revision
`ca-test-athon-test-un-001--0000015`. Local `POSTGRES_HOST` also remains unchanged.
The ignored `.env` contains the new credentials in `MIGRATION_TARGET_*` settings.

For a later authorized switch:

1. Check whether the source has changed since the snapshot. Any new records,
   uploads, reviews, associations or account changes require synchronization
   before switching. This copy does not continuously replicate new changes.
2. Set `POSTGRES_HOST` to `enginex-postgresql.postgres.database.azure.com`.
3. Update the `postgres-password` Container App secret to the new destination
   password, retaining the `POSTGRES_PASSWORD` secret reference. A hostname-only
   switch will fail because the two servers now have different passwords.
4. Keep `POSTGRES_DB=enginex`, `POSTGRES_USER=psqladmin`, `POSTGRES_PORT=5432` and
   `POSTGRES_SSLMODE=require`. Refresh/restart the appropriate app revision, then
   verify login, portfolio data, document sources, AI and the extraction worker.
5. For local development, use the same destination host and password in the
   normal `POSTGRES_*` variables, then restart the local server. Mac network
   reachability is separate from the verified Container App connectivity.

PDFs remain in `sastestathonun001/storagex`. Keep the existing storage and AI
configuration after switching. Retain the old database until the switch is
verified and its retirement is separately authorized.
