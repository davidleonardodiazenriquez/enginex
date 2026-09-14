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
