# Enginex

Containerized Django base application for deployment to Azure Container Apps.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://localhost:8000>. Health checks are available at
<http://localhost:8000/health/>.

## Docker

```bash
docker build -t enginex:local .
docker run --rm -p 8000:8000 \
  -e DJANGO_ENVIRONMENT=development \
  enginex:local
```

## CI/CD configuration

The GitHub Actions workflow tests and builds changes. Security scans and the
runtime-package assertion are disabled for this hackathon at the project owner's
request. When Azure workload identity is configured, pushes to `main` also
publish images to `acrtestathonun001` using the commit SHA and `latest` tags and
deploy to Container Apps.

Until that identity is configured, releases use the developer's signed-in Azure
CLI session to build in ACR and update the Container App. Run relevant tests and
verify the changed behavior live. Workflow or documentation changes alone do not
require rebuilding and redeploying the application.

Configure these GitHub repository variables for Azure workload identity
federation:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

The federated identity needs `AcrPush` on `acrtestathonun001`. No Azure password
or registry credential should be stored in GitHub.

## Runtime configuration

Copy `.env.example` when developing locally. Production secrets must be stored
in Azure Key Vault or Container Apps secrets, never committed to Git.

SQLite is included only for the starter application. Use Azure Database for
PostgreSQL before adding persistent production data. Set the `POSTGRES_*`
variables documented in `.env.example` to enable PostgreSQL; when they are not
set, local development and unit tests use SQLite.

The deployed application must receive `POSTGRES_PASSWORD` through an Azure
Container Apps secret. Never store the database password in source control or
GitHub variables.

An administrator can initialize the configured database without placing the
password on the command line:

```bash
POSTGRES_HOST=your-server.postgres.database.azure.com \
POSTGRES_USER=your-admin-user \
POSTGRES_DB=enginex \
python scripts/setup_database.py
```

## Portfolio map

After login, `/` opens the interactive Abu Dhabi portfolio map. All six locations
open their own asset dashboard after the additive demo population command runs.
`/reports/` combines synthetic records and document-backed evidence with per-value
provenance. `/contracts/` supports local PDF upload, Azure Storage selection,
EnginexAI extraction, manual association, review and source-page navigation.

See [the demo walkthrough](docs/demo-walkthrough.md) for the story, operating
steps, provenance rules and known limits. The original Al Rayyana summary is
preserved separately from the new synthetic record sample.

```sh
python manage.py migrate
python manage.py populate_portfolio
python manage.py process_contracts --loop
```

Run the extraction worker alongside the local web server. The Container App
starts both automatically through `scripts/start.sh`. Install Poppler locally
(`brew install poppler` on macOS) for rendered PDF page previews; it is included
in the container image.

Configure `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` (a reference
to the `azure-storage-key` Container App secret), and `AZURE_STORAGE_CONTAINER`.
The target is `sastestathonun001/storagex`. Local development without Azure uses
ignored `private-media/` storage. Production requires configured Azure storage.

Leaflet 1.9.4 and its BSD license are bundled under `core/static/core/vendor`.
Satellite tiles load directly from Esri World Imagery and street tiles from
OpenStreetMap, with attribution on the map. These require browser internet access.
If tiles fail, the location list and report links remain usable.

Design reference: [World of Aldar](https://world.aldar.com/uae).
Property photos are from Aldar's [Al Rayyana](https://www.aldar.com/en/explore-aldar/businesses/development/residential/other-destinations/al-rayyana),
[Gate & Arc](https://www.aldar.com/properties/en/uae/reem-island/gate),
[Sas Al Nakhl](https://www.aldar.com/en/explore-aldar/businesses/investment/retail/communities/sas-al-nakhl),
[Eastern Mangroves](https://www.aldar.com/en/explore-aldar/businesses/investment/retail/communities/eastern-mangroves),
and [The Bridges](https://cloudliving.aldar.com/en/the-bridges) pages. Gate and Arc
share district photography. Pins indicate community locations, not property
boundaries. The Bridges II is placed near Tower 4 using the
[map listing](https://yandex.com/maps/org/the_bridges_tower_4/12164780943/);
[Arc](https://yandex.com/maps/11498/abu-dhabi/house/YU0YcgdpT0ECQFxufXh4dH5mZw%3D%3D/),
[Sas Al Nakhl](https://yandex.com/maps/11498/abu-dhabi/geo/5167669792/),
and [Al Rayyana's street location](https://yandex.com/maps/11498/abu-dhabi/geo/5185447516/)
were cross-checked. Exact asset boundaries and phase coverage can be added with
the additional asset data.

## Azure AI Foundry chat

The dashboard chat uses a server-side proxy. Configure these Container App
environment variables:

- `AZURE_AI_FOUNDRY_ENDPOINT`
- `AZURE_AI_FOUNDRY_API_KEY` (secret reference)
- `AZURE_AI_FOUNDRY_DEPLOYMENT`
- `AZURE_AI_FOUNDRY_API_VERSION` (optional; defaults to `2024-10-21`)

The API key is never returned to the browser.

For every authenticated chat request, Django reads the same asset displayed on
the dashboard and sends its facts, tenant revenue shares, vacancies, and renewal
and rent metrics to the model. Amounts are explicitly labelled as AED millions;
totals are calculated by the application. The assistant identifies the sample
data, cites dashboard sections, and explains missing information rather than
inventing it. This covers the selected dashboard asset, its synthetic record sample, and the
latest successful extractions for up to 20 associated document records. The
assistant receives source labels, page quotations and review status. Unassigned
contracts remain in the contract workspace/report rather than being silently
assigned to a map location. It cannot execute SQL or change records.

The browser includes the last three successful question/answer pairs for
follow-ups. History stays in the current page and resets on refresh; database
data is read again for every message. The document-backed demo adds an additive schema migration.

For EnginexAI, use `AZURE_AI_FOUNDRY_ENDPOINT=https://<resource>.openai.azure.com/openai/v1/`
and set `AZURE_AI_FOUNDRY_DEPLOYMENT` to the deployment name, for example `your-deployment-name`.
The v1 base URL and a complete `/openai/v1/chat/completions` URL are both supported.
The dated API version setting is ignored for v1 endpoints. Requests use
`max_completion_tokens` with a 4,096-token budget for reasoning and output, and
omit custom temperature values.

Resource-root URLs and full legacy deployment URLs remain supported. A resource
root uses the dated API unless `AZURE_AI_FOUNDRY_API_VERSION` is `v1` or `preview`.
Provider failures log the HTTP status and error identifiers without logging the
API key, prompts, or upstream error messages. The chat subtitle indicates setup,
not a live connectivity check.

## EnginexAI

`/enginex-ai/` provides portfolio-wide EnginexAI analysis, read-only database queries,
PDF evidence links and calculated bar, line and doughnut charts. A persistent
bottom composer is available on all authenticated app pages. The layout adapts
to mobile Safari with bottom navigation and keyboard-aware input positioning.
See the demo walkthrough for example prompts, provenance and supported scope.
