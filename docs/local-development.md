# Local PostgreSQL development

The Django app and PostgreSQL run on this Mac. Source PDFs remain in private Azure
Storage, and EnginexAI calls the configured Azure endpoint over HTTPS. Local
coding, database queries and login need no Azure CLI session or deployment.
Storage and AI still need internet access and their existing `.env` credentials.

## Daily use

```sh
make dev     # Starts local PostgreSQL if stopped, then http://127.0.0.1:8000.
make worker  # In a second terminal, process locally queued contract extractions.
```

The app opens directly as `demo` with no login form. Local `.env` enables
`DJANGO_LOCAL_DEMO_AUTO_LOGIN=true`; this applies only in development mode.
The hosted presentation app uses explicit `DJANGO_DEMO_AUTO_LOGIN=true` to
provide the same direct workspace access with production settings. Visitors
receive a regular `demo` session; `/admin/` still requires administrator login.
Set the hosted flag to `false` to restore workspace sign-in. No password changes
are needed for this mode, and the demo account must not have staff privileges.
Direct report, PDF and chat links also create a demo session. Document actions
remain attributed to that account. Sign out controls are hidden in this mode.
The local demo password was updated as requested; it is stored as a database
password hash. To return to normal login, set the flag to `false` and restart the
web server. `/admin/` continues to use the separate administrator login.

The presentation interface uses normal portfolio language. Demo/synthetic labels
have been replaced on the map, dashboards, 3D views, reports and AI chart cards;
the presenter explains the data's status verbally. Stored baseline values, origin
metadata, CSV provenance and original contract quotations/PDFs remain unchanged.
Generated record and unit codes display with `PR-` in place of `DEMO-`; both forms
are searchable. AI uses the same presentation language for routine replies and
answers provenance questions truthfully. Existing conversation messages retain
their original text; use **New conversation** for a fresh presentation.

Ctrl+C stops the web server or worker. The database keeps running and its data
persists. Stop the app and worker before running `make db-stop`. After a reboot,
`make dev` starts the database again. There is no global login service to manage.

```sh
make db-status
make db-shell   # psql connected to this local database; \q exits.
make db-stop
```

The project uses Homebrew PostgreSQL 18, matching Azure's major version, on
`127.0.0.1:5433`. Its data lives in `.local/postgres/`, and its log is
`.local/postgres.log`. Both are ignored by Git and Docker. Do not delete that
directory to fix a startup problem; it contains the local data. The Homebrew
installation's separate default cluster is unused.

The root `.env` is loaded automatically. Exported shell variables take precedence.
Variable interpolation is disabled so `${...}` inside passwords stays literal.
Restart the web server and worker after changing `.env`. Python edits reload in
the web server; refresh the browser for template/static changes. Restart the
worker after changing its Python code.

## First setup on another checkout

```sh
brew install postgresql@18 poppler
make setup
```

Create `.env` from `.env.example`, choose a local PostgreSQL password, and fill in
actual Azure Storage and AI credentials. Preserve an existing `.env`. Then:

```sh
make db-init
```

This creates a separate, password-protected PostgreSQL cluster reachable only
through loopback TCP. Repeating it preserves existing databases and records.
`POSTGRES_BIN` can specify a PostgreSQL 18 binary directory on a machine without
Homebrew. The helper refuses cloud database hosts.

A new cluster has no application data. Restore a verified Azure snapshot into its
empty `enginex` database before starting the app. For an intentionally fresh demo
instead, run `manage.py migrate`, `manage.py populate_portfolio`, and create an
administrator with `manage.py createsuperuser`. A fresh database also needs an
active `demo` user for automatic local access. Do not use `seed_demo` to refresh
an existing database; it can alter accounts and data.

## Data boundaries

Resident feedback, NPS calculation and local sentiment analysis are documented in
[Resident feedback](resident-feedback.md), including population/analysis commands
and the additive migration needed for the next release.

Generated occupied leases and tenant rankings use fictional person names in
English letters, including transliterated Arabic names. Names remain stable for
each record. To update placeholders on an existing database, run:

```sh
.venv/bin/python manage.py name_portfolio_tenants
```

This repeatable command changes only generated tenant placeholders and matching
dashboard labels. It preserves custom names, vacant units, financial values and
document evidence. New `populate_portfolio` records already use person names.
Include this command when applying these data changes in a future release; do
not rerun `seed_demo` against an existing database.

Location matching runs after each successful contract extraction. A unique,
explicit premises match with a valid page quotation links the contract's own
record to that asset. It does not merge into a generated unit or replace any
baseline values. Ambiguous, conflicting, missing or unlisted locations appear
under **Contracts → Needs location review**, with a reason and a manual form.
Manual decisions, including **Outside portfolio**, are preserved. Rejecting the
premises evidence or extracting conflicting new premises returns an automatic
association to review; the audit history retains its earlier source pages.

Migration `core.0003_contract_location_resolution` adds the status and audit
metadata. Existing extracts can be matched without another model call:

```sh
.venv/bin/python manage.py resolve_contract_locations
```

This command is idempotent and preserves existing manual associations. It was
applied locally: two Eastern Mangroves contracts linked automatically, ten need
review, and one earlier outside-portfolio decision was preserved. Source PDFs,
extracted fields, record IDs and baseline data were unchanged. Apply the migration
and run this command against the explicitly selected Azure database only as part
of a future authorized release.

This Mac uses an independent snapshot of the currently serving Azure database,
including accounts, six locations, synthetic leases, extracted contract fields
and document provenance. Database edits, password changes, reviews and extraction
jobs now stay local. They do not automatically appear in the deployed app, and
later Azure changes do not automatically appear locally.

The PDFs still use `sastestathonun001/storagex`. Existing document links read their
original immutable PDF snapshots. New local uploads save PDFs in that same Azure
container but create database records and extraction jobs only in the local
database. Therefore `make worker` is required to process local jobs; the Azure
worker cannot see them. PDF page previews require Poppler. Image-only documents
still require an OCR integration, which is not configured.

The original Azure connection values were preserved in the ignored
`.local/azure-source.env`. `.env` retains the separate `MIGRATION_TARGET_*` values
for the new Azure server, but these are not used by the running local app. Never
copy local `POSTGRES_*` values to the Container App.

## Refreshing the local snapshot

Direct TCP 5432 to either Azure server timed out on this Mac while traffic used
Zscaler/tunnel `utun4`. The local database removes that dependency. To obtain the
initial copy, a temporary ACR task ran a consistent native `pg_dump` in Azure,
saved it to a private temporary Storage blob, and this Mac downloaded it over
HTTPS. The temporary cloud blobs were then removed.

Native snapshots and their verification manifests are in `.local/backups/`.
They contain database records and must stay outside Git/build contexts. A future
refresh should export from the currently serving Azure host, then restore into a
new empty local database. Preserve local work first; never refresh by blindly
restoring over the working database. Check dump hashes, table contents, sequence
values and authenticated app behavior before switching to a refreshed copy.

## Validation and releases

```sh
make check
make test
.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

Tests use an isolated SQLite database with Azure configuration disabled. A plain
`manage.py test` selects the same settings unless explicitly overridden. Tests use
PDF fixtures and mocked model responses; separately exercise the local app for
actual PostgreSQL queries, Storage reads and AI calls. `/health/` reports web
liveness only.

Setup verification on 2026-09-15 passed: all 19 restored tables, 17 sequences and
the schema matched the source snapshot; 58 isolated tests and migration checks
passed. The local app served 11 authenticated pages, opened a report's Azure PDF
with a matching SHA256, and generated a real EnginexAI chart covering all six
locations and 720 synthetic records. The iPhone 16 Pro Max WebKit check found no
horizontal overflow and kept the input visible. Database stop/start and repeat
initialization preserved the data. The worker started against the local queue;
the 13 already completed contracts were not reprocessed during setup.

For a schema change, create Django migrations and apply them locally with
`manage.py migrate`. Later deploy the code and apply those reviewed migrations
against the selected Azure database. Demo-data changes require an explicit,
additive import with stable identifiers and provenance. Do not replace Azure
accounts, contract records or the entire Azure database with this development
snapshot.

The current local refactor and database setup have not been deployed. The live
Container App still points to the original Azure PostgreSQL server. A separate
copy was already verified on `enginex-postgresql.postgres.database.azure.com`;
see [database migration](database-migration.md) for its snapshot time and pending
cutover. Select the intended Azure database explicitly at release time.

## Code layout

- `core/portfolio/`: map locations, dashboard context and property scenes.
- `core/documents/`: storage, ingestion, extraction and document views.
- `core/reports/`: report queries, views and exports.
- `core/ai/`: portfolio queries, model tools, analyst service and chat views.
- `core/integrations/`: AI provider transport.
- `core/models.py` and `core/migrations/`: shared database schema.
- `core/tests/`: isolated regression tests.
