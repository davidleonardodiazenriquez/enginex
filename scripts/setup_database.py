#!/usr/bin/env python3
"""Create the application database and apply Django migrations securely."""

import getpass
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql


def required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} must be set")
    return value


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    host = required_environment("POSTGRES_HOST")
    user = required_environment("POSTGRES_USER")
    database = os.getenv("POSTGRES_DB", "enginex").strip()
    port = os.getenv("POSTGRES_PORT", "5432")
    sslmode = os.getenv("POSTGRES_SSLMODE", "require")
    password = os.getenv("POSTGRES_PASSWORD") or getpass.getpass("PostgreSQL password: ")

    connection_options = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sslmode": sslmode,
        "connect_timeout": 10,
    }

    with psycopg.connect(dbname="postgres", autocommit=True, **connection_options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
                print(f"Created database {database}")
            else:
                print(f"Database {database} already exists")

    os.environ.update(
        {
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": port,
            "POSTGRES_DB": database,
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_SSLMODE": sslmode,
            "DJANGO_SETTINGS_MODULE": "config.settings",
        }
    )

    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False)

    with psycopg.connect(dbname=database, **connection_options) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
            )
            table_count = cursor.fetchone()[0]
    print(f"Verified {table_count} public tables in {database}")


if __name__ == "__main__":
    main()
