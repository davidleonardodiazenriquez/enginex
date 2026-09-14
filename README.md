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

The GitHub Actions workflow tests and scans every change. Pushes to `main` also
publish images to `acrtestathonun001` using the commit SHA and `latest` tags.

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

## Azure AI Foundry chat

The dashboard chat uses a server-side proxy. Configure these Container App
environment variables:

- `AZURE_AI_FOUNDRY_ENDPOINT`
- `AZURE_AI_FOUNDRY_API_KEY` (secret reference)
- `AZURE_AI_FOUNDRY_DEPLOYMENT`
- `AZURE_AI_FOUNDRY_API_VERSION` (optional; defaults to `2024-10-21`)

The API key is never returned to the browser.

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
