# Enginex in az_subscription_01

The owner requested an independent deployment in this tenant on 2026-09-16.
Keep local development on the local PostgreSQL instance; never upload `.env`.

| Resource | Destination |
| --- | --- |
| Subscription | `9119b270-ccef-4d7f-b402-0d6f4862b1ad` (`az_subscription_01`) |
| Tenant | `3de515ab-9ec9-4d77-9472-c0ea5d0a698a` |
| Azure CLI account | `davidleonardodiaz@outlook.com` |
| Resource group | `rg-enginex-demo-uaenorth` |
| Region | UAE North |
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

The Foundry endpoint, deployment and API key must all come from this tenant.
Azure initially refused creation of the requested model deployment in the new
`ai-enginex9119` account with error `715-123420` (unusual account activity).
Resolve the account restriction with Azure support, or use a separately approved,
already available deployment. Do not silently fall back to the original tenant.
Read the current `AZURE_AI_FOUNDRY_*` configuration privately when troubleshooting;
do not print or commit keys. Model compatibility is documented in
[the demo walkthrough](demo-walkthrough.md).

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
