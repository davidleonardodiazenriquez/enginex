#!/usr/bin/env python3
"""Copy one PostgreSQL database into a new database, then verify its contents.

Run with PostgreSQL client tools and psycopg2 in a temporary migration container.
SOURCE_POSTGRES_* and TARGET_POSTGRES_* supply host, port, user, password and DB.
The target database must not exist. This script never updates the application.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import psycopg2
from psycopg2 import sql


def emit(event, **details):
    print(json.dumps({"event": event, **details}, default=str), flush=True)


def config(prefix):
    result = {
        "host": os.environ[f"{prefix}_POSTGRES_HOST"],
        "port": os.environ.get(f"{prefix}_POSTGRES_PORT", "5432"),
        "user": os.environ[f"{prefix}_POSTGRES_USER"],
        "password": os.environ[f"{prefix}_POSTGRES_PASSWORD"],
        "dbname": os.environ.get(f"{prefix}_POSTGRES_DB", "enginex"),
        "sslmode": "require",
        "connect_timeout": 15,
    }
    if not all(result.values()):
        raise RuntimeError(f"Incomplete {prefix} configuration")
    return result


def client_environment(settings):
    env = os.environ.copy()
    for field, name in [("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"),
                        ("password", "PGPASSWORD"), ("dbname", "PGDATABASE")]:
        env[name] = settings[field]
    env.update(PGSSLMODE="require", PGCONNECT_TIMEOUT="15", PGOPTIONS="-c timezone=UTC -c client_min_messages=warning")
    return env


def run_client(command, settings):
    result = subprocess.run(command, env=client_environment(settings), capture_output=True, text=True, timeout=300)
    if result.returncode:
        # Do not print failing SQL, row contents or secret-bearing process arguments.
        emit("client_failed", tool=command[0], exit_code=result.returncode)
        raise RuntimeError(f"{command[0]} failed; target will not be considered verified")
    if result.stderr.strip():
        emit("client_warning", tool=command[0], warning_lines=len(result.stderr.splitlines()))
        raise RuntimeError(f"Unexpected {command[0]} warnings require review")
    return result.stdout


def normalize_index(row):
    """Accept only the two equivalent renderings of our known status predicate."""
    schema, table, name, definition = row
    if (schema, table, name) == ("public", "core_extractionrun", "one_active_extraction_per_document"):
        old = "ANY ((ARRAY['queued'::character varying, 'running'::character varying])::text[])"
        restored = "ANY (ARRAY[('queued'::character varying)::text, ('running'::character varying)::text])"
        definition = definition.replace(restored, old)
    return schema, table, name, definition


def manifest(connection):
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        cursor.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
        tables = cursor.fetchall()
        data = {}
        for schema, table in tables:
            cursor.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {}.{} t").format(sql.Identifier(schema), sql.Identifier(table)))
            rows = sorted(row[0].encode("utf-8") for row in cursor.fetchall())
            digest = hashlib.sha256()
            for row in rows:
                digest.update(len(row).to_bytes(8, "big"))
                digest.update(row)
            data[f"{schema}.{table}"] = {"rows": len(rows), "sha256": digest.hexdigest()}
        cursor.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
        sequence_names = cursor.fetchall()
        sequences = {}
        for schema, name in sequence_names:
            cursor.execute(sql.SQL("SELECT last_value,is_called FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(name)))
            sequences[f"{schema}.{name}"] = list(cursor.fetchone())
        schema_queries = {
            # A native restore removes physical slots left by dropped columns;
            # compare the visible column order, not those obsolete slot numbers.
            "columns": "SELECT table_schema,table_name,column_name,row_number() OVER (PARTITION BY table_schema,table_name ORDER BY ordinal_position),column_default,is_nullable,data_type,udt_name,character_maximum_length,numeric_precision,numeric_scale,is_identity,identity_generation,identity_start,identity_increment FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,4",
            "indexes": "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3",
            "constraints": "SELECT n.nspname,c.relname,p.conname,p.contype,p.convalidated,pg_get_constraintdef(p.oid) FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3",
            "extensions": "SELECT extname,extversion FROM pg_extension ORDER BY 1",
            "triggers": "SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3",
            "views": "SELECT schemaname,viewname,definition FROM pg_views WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2",
            "functions": "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND p.prokind IN ('f','p') ORDER BY 1,2,3",
        }
        schema = {}
        for name, query in schema_queries.items():
            cursor.execute(query)
            schema[name] = cursor.fetchall()
        schema["indexes"] = [normalize_index(row) for row in schema["indexes"]]
        schema_digest = hashlib.sha256(json.dumps(schema, default=str, sort_keys=True).encode()).hexdigest()
        return {"tables": data, "sequences": sequences, "schema_sha256": schema_digest}


def main():
    source_config, target_config = config("SOURCE"), config("TARGET")
    if source_config["host"].lower() == target_config["host"].lower():
        raise RuntimeError("Source and target must be different servers")
    for tool in ("pg_dump", "pg_restore"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} is required")

    source = psycopg2.connect(**source_config)
    admin = psycopg2.connect(**{**target_config, "dbname": "postgres"})
    try:
        source.set_session(isolation_level="REPEATABLE READ", readonly=True)
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtext(%s))", ("enginex-database-copy:" + target_config["dbname"],))
            cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target_config["dbname"],))
            if cursor.fetchone():
                raise RuntimeError("Target database already exists; refusing to overwrite it")
            cursor.execute("SHOW server_version_num")
            target_version = int(cursor.fetchone()[0])
        with source.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            source_version = int(cursor.fetchone()[0])
            if target_version // 10000 < source_version // 10000:
                raise RuntimeError("PostgreSQL major-version downgrade is not supported")
            cursor.execute("SELECT pg_export_snapshot(),clock_timestamp()")
            snapshot, snapshot_time = cursor.fetchone()
            cursor.execute("SELECT pg_encoding_to_char(encoding),datcollate,datctype,datlocprovider FROM pg_database WHERE datname=current_database()")
            encoding, collate, ctype, provider = cursor.fetchone()
            if provider != 'c':
                raise RuntimeError("This migration requires explicit handling of non-libc locales")
            cursor.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")
            owners = {row[0] for row in cursor.fetchall()}
            if owners != {source_config["user"]}:
                raise RuntimeError("Multiple table owners require an explicit ownership mapping")
        before = manifest(source)
        emit("snapshot_ready", snapshot_at=snapshot_time, source_version=source_version, target_version=target_version,
             tables=len(before["tables"]), rows={name: item["rows"] for name, item in before["tables"].items()})

        with tempfile.TemporaryDirectory(prefix="enginex-db-copy-") as directory:
            dump = str(Path(directory) / "enginex.dump")
            run_client(["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--no-password",
                        "--lock-wait-timeout=10s", "--snapshot=" + snapshot, "--file=" + dump], source_config)
            dump_digest = hashlib.sha256(Path(dump).read_bytes()).hexdigest()
            emit("dump_complete", bytes=Path(dump).stat().st_size, sha256=dump_digest)
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {} WITH TEMPLATE template0 ENCODING {} LC_COLLATE {} LC_CTYPE {} LOCALE_PROVIDER libc OWNER {}").format(
                    sql.Identifier(target_config["dbname"]), sql.Literal(encoding), sql.Literal(collate), sql.Literal(ctype), sql.Identifier(target_config["user"])))
            emit("target_created", host=target_config["host"], database=target_config["dbname"])
            run_client(["pg_restore", "--no-owner", "--no-privileges", "--no-password", "--single-transaction", "--clean", "--if-exists",
                        "--exit-on-error", "--dbname=" + target_config["dbname"], dump], target_config)
            emit("restore_complete")
            target = psycopg2.connect(**target_config)
            try:
                target.set_session(isolation_level="REPEATABLE READ", readonly=True)
                after = manifest(target)
            finally:
                target.close()
            if before != after:
                mismatches = [name for name in before if before[name] != after[name]]
                emit("verification_failed", mismatched_sections=mismatches)
                raise RuntimeError("Restored database did not match the source snapshot")
            emit("migration_verified", source=source_config["host"], target=target_config["host"], database=target_config["dbname"],
                 snapshot_at=snapshot_time, tables=len(after["tables"]), sequences=len(after["sequences"]),
                 rows={name: item["rows"] for name, item in after["tables"].items()},
                 schema_sha256=after["schema_sha256"], all_table_contents_match=True, all_sequences_match=True,
                 application_connection_changed=False)
    finally:
        source.close()
        admin.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit("migration_stopped", error_type=type(exc).__name__,
             reason=str(exc) if isinstance(exc, RuntimeError) else "Database/tooling error; inspect the destination before retrying")
        raise SystemExit(1) from None
