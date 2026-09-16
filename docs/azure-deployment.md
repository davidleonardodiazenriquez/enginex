# Enginex in az_subscription_01

The owner requested an independent deployment in this tenant on 2026-09-16.
Keep local development on the local PostgreSQL instance; never upload `.env`.

| Resource | Destination |
| --- | --- |
| Subscription | `9119b270-ccef-4d7f-b402-0d6f4862b1ad` (`az_subscription_01`) |
| Tenant | `3de515ab-9ec9-4d77-9472-c0ea5d0a698a` |
| Azure CLI account | `davidleonardodiaz@outlook.com` |
| Resource group | `rg-enginex-demo-uaenorth` |
| App / database / storage region | UAE North |
| Foundry account | `az-foundry-02-main` in `az-rg-02`, East US |
| AI deployment | `gpt-6-astra`, version `2026-09-03` |
| Registry | `acrenginex9119.azurecr.io` |
| Container Apps environment | `cae-enginex-demo` |
| Container App | `ca-enginex-demo` |
| Pull identity | `id-enginex-demo`, AcrPull scoped to the new registry |
| PostgreSQL | `enginex-postgresql.postgres.database.azure.com` in `az-rg-01` |
| Database | `enginex_live`, port 5432, user `psqladmin`, SSL required |
| Document storage | `stenginex9119/storagex`, private blobs |
| Website | `https://ca-enginex-demo.thankfulsky-34b83cfe.uaenorth.azurecontainerapps.io/` |

## Data migration

A consistent snapshot of the original serving Azure database was taken at
2026-09-16 09:09:13 UTC and restored into the **new** `enginex_live` database.
The older `enginex` database on the destination server was preserved. All 20
tables, 18 sequences, schema definitions, account hashes and row contents matched.
The snapshot includes six assets, 733 records, 13 contracts, 372 extracted fields,
three association events, and 300 resident feedback transcripts.

All 1,026 blobs (234,578,278 bytes) were copied from the original `storagex`
container and verified with SHA-256 against the destination. Immutable PDF paths
remain unchanged, so document field/page links can use the new account directly.
Copying the unprocessed PDF library does not enqueue extraction or create leases.

This is a point-in-time copy, not ongoing replication. Leave the original app,
database and storage intact until their retirement is explicitly requested.
New activity in either tenant does not automatically appear in the other.

## Application configuration

Use Container App secrets for Django signing, PostgreSQL, Storage and Foundry.
Preserve `DJANGO_ENVIRONMENT=production`, `DJANGO_DEMO_AUTO_LOGIN=true`, explicit
allowed hosts and HTTPS CSRF origins. `/admin/` retains its separate login.
A new Django signing key isolates sessions from the original installation;
existing user password hashes are retained by the database copy.

The app uses the owner's model deployment in `az-foundry-02-main`, in the new
tenant. Its endpoint is
`https://az-foundry-02-main.cognitiveservices.azure.com/openai/v1`, with API version
`v1`. Real greetings, database tools, charts and follow-up questions passed.
Azure initially blocked model creation in the newly created `ai-enginex9119`
account; the owner then deployed the model in the existing Foundry account above.
The empty unused account was removed after verifying it had no deployments.
Read current `AZURE_AI_FOUNDRY_*` values privately when troubleshooting; do not
print or commit keys. Model compatibility is documented in
[the demo walkthrough](demo-walkthrough.md).

The app uses 2 CPU / 4 GiB, one to three replicas and HTTP concurrency 10.
Gunicorn and the document worker run together through `scripts/start.sh`.
This migration did not change local `.env`: local PostgreSQL and its existing
Storage/AI connections remain as configured. Changing local cloud services is
separate from this hosted cutover and requires restarting local web/worker
processes; never replace local PostgreSQL with the hosted connection by accident.

## Verified release — 2026-09-16

- Serving source: `394ac89f83e2903f29d103bf0cd50d58fec6ab05`, ACR build `dg2`.
- Image: `acrenginex9119.azurecr.io/enginex@sha256:8e27fc1845967c7d37027184793f6001a573c8577b22d6b31d1dc47cedc6c291`.
- Ready revision: `ca-enginex-demo--7bv7tbc`, single revision, 100% traffic.
- GitHub run `35078316876`: 109 tests and image build passed; Azure deployment
  remained skipped, as expected for the manual Azure CLI release workflow.
- Fresh visitor access, all six asset pages, reports, contracts, feedback, AI and
  Process passed (13 routes). `/admin/` still requires administrator login.
- All 13 source PDFs opened through the app and matched their SHA-256 hashes.
- AI produced the six-property NPS chart from 300 transcripts (global +31.7),
  opened supporting feedback and answered a follow-up correctly.
- Desktop and iPhone WebKit Process checks passed in normal and expanded modes.
  The actual rendered QR decoded to this new website in all four combinations.
- Snapshot hashes cover all 20 tables and 18 sequences; all 1,026 copied blobs
  were re-downloaded and verified. Pending library PDFs were not processed.

Sanitized evidence is in ignored `tmp/new-tenant-release.json`,
`tmp/new-tenant-database.json`, `tmp/new-tenant-storage.json`,
`tmp/new-tenant-data-checks.json`, `tmp/foundry-new-tenant-checks.json` and
`tmp/process-qr-checks.json`. Query Azure when those local artifacts are absent.
Documentation-only follow-up commits do not change the serving source above.

## Releases

1. Verify the Azure account and use the explicit subscription above for every
   operation. Run relevant checks and commit only the intended source changes.
2. Build a `git archive` of that commit in the new ACR with `az acr build`, tagging
   the full SHA. No security scans are required for this hackathon.
3. Resolve the successful run's immutable digest. Apply migrations only when
   required, to `enginex_live`. Never run `seed_demo` on an existing deployment.
4. Update only the new app's image, preserving secrets, identity, ingress and
   scale settings. Verify the ready revision and actual application behavior.
5. Check fresh visitor access, property/report views, PDF retrieval, feedback,
   AI database tools and charts, and the Process page's new QR destination.

The GitHub workflow targets these new resources. Repository subscription and
tenant variables must match the table. `AZURE_CLIENT_ID` is still unconfigured,
so GitHub performs tests/builds while publishing and deployment use the owner's
local Azure CLI login. Do not reuse an unrelated app's federated identity.
