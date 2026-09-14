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

After login, `/` opens the interactive Abu Dhabi portfolio map. The six
community locations are configured in `core/locations.py`. Al Rayyana opens
`/assets/al-rayyana/` with the existing metrics and AI assistant; the five other
locations show previews with "Metrics coming soon" and have no fabricated
financial records. The map reads Al Rayyana's home/building counts from the
database. Search, readiness filters, nearby-location grouping, pan/zoom, a reset
control, and satellite/street styles work on desktop and mobile. Reduced-motion
preferences disable animated camera moves. No schema migration is required.

Leaflet 1.9.4 and its BSD license are bundled under `core/static/core/vendor`.
Satellite tiles load directly from Esri World Imagery and street tiles from
OpenStreetMap, with attribution on the map. These require browser internet access.
If tiles fail, the location list and Al Rayyana metrics link remain usable.

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
inventing it. This covers the current dashboard asset, not other database tables
or a portfolio-wide query interface. It cannot execute SQL or change records.

The browser includes the last three successful question/answer pairs for
follow-ups. History stays in the current page and resets on refresh; database
data is read again for every message. No database migration is needed for chat.

For Astra, use `AZURE_AI_FOUNDRY_ENDPOINT=https://<resource>.openai.azure.com/openai/v1/`
and set `AZURE_AI_FOUNDRY_DEPLOYMENT` to the deployment name, such as `gpt-6-astra`.
The v1 base URL and a complete `/openai/v1/chat/completions` URL are both supported.
The dated API version setting is ignored for v1 endpoints. Requests use
`max_completion_tokens` with a 4,096-token budget for reasoning and output, and
omit custom temperature values.

Resource-root URLs and full legacy deployment URLs remain supported. A resource
root uses the dated API unless `AZURE_AI_FOUNDRY_API_VERSION` is `v1` or `preview`.
Provider failures log the HTTP status and error identifiers without logging the
API key, prompts, or upstream error messages. The chat subtitle indicates setup,
not a live connectivity check.
