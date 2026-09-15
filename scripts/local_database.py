"""Manage this checkout's PostgreSQL 18 cluster; never connect to Azure."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"


def configuration():
    values = {**dotenv_values(ROOT / ".env", interpolate=False), **os.environ}
    if values.get("POSTGRES_HOST") not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Local database commands require POSTGRES_HOST=127.0.0.1 in .env.")
    if values.get("POSTGRES_SSLMODE") != "disable":
        raise RuntimeError("This loopback-only cluster requires POSTGRES_SSLMODE=disable.")
    if not all(values.get("POSTGRES_" + key) for key in ("USER", "PASSWORD", "DB", "PORT")):
        raise RuntimeError("Set POSTGRES_USER, PASSWORD, DB and PORT in .env first.")
    port = int(values["POSTGRES_PORT"])
    if not 1024 <= port <= 65535:
        raise RuntimeError("Choose a local PostgreSQL port between 1024 and 65535.")
    return {
        "host": "127.0.0.1", "port": port, "dbname": values["POSTGRES_DB"],
        "user": values["POSTGRES_USER"], "password": values["POSTGRES_PASSWORD"],
        "sslmode": "disable", "connect_timeout": 5,
    }


def binaries():
    if os.environ.get("POSTGRES_BIN"):
        directory = Path(os.environ["POSTGRES_BIN"])
    else:
        prefix = subprocess.check_output(["brew", "--prefix", "postgresql@18"], text=True).strip()
        directory = Path(prefix) / "bin"
    version = subprocess.check_output([str(directory / "pg_ctl"), "--version"], text=True)
    if "(PostgreSQL) 18." not in version:
        raise RuntimeError("Install PostgreSQL 18: brew install postgresql@18")
    return directory


def running(bin_dir):
    return subprocess.run([str(bin_dir / "pg_ctl"), "-D", str(DATA), "status"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def start(bin_dir, config):
    if not (DATA / "PG_VERSION").exists():
        raise RuntimeError("Run make db-init to create the local cluster first.")
    if not running(bin_dir):
        # Disable Unix sockets: this dedicated cluster is reached on loopback TCP only.
        subprocess.run([str(bin_dir / "pg_ctl"), "-D", str(DATA), "-l", str(LOCAL / "postgres.log"),
                        "-o", f"-h 127.0.0.1 -p {config['port']} -k ''", "-w", "start"], check=True)
    with psycopg.connect(**{**config, "dbname": "postgres"}) as connection:
        actual = connection.execute("SHOW data_directory").fetchone()[0]
        if Path(actual).resolve() != DATA.resolve():
            raise RuntimeError("The configured port belongs to a different PostgreSQL cluster.")


def initialize(bin_dir, config):
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        with tempfile.NamedTemporaryFile(mode="w", dir=LOCAL) as password_file:
            password_file.write(config["password"] + "\n")
            password_file.flush()
            subprocess.run([str(bin_dir / "initdb"), "-D", str(DATA), "-U", config["user"],
                            "--encoding=UTF8", "--locale=en_US.UTF-8", "--auth=scram-sha-256",
                            "--pwfile=" + password_file.name], check=True)
    start(bin_dir, config)
    with psycopg.connect(**{**config, "dbname": "postgres"}, autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (config["dbname"],)).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(config["dbname"])))
    print(f"Local database ready at 127.0.0.1:{config['port']}/{config['dbname']}. Existing data preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "start", "stop", "status", "shell"))
    action = parser.parse_args().action
    config = configuration()
    bin_dir = binaries()
    if action == "init":
        initialize(bin_dir, config)
    elif action == "start":
        start(bin_dir, config)
    elif action == "stop":
        if running(bin_dir):
            subprocess.run([str(bin_dir / "pg_ctl"), "-D", str(DATA), "-m", "fast", "-w", "stop"], check=True)
        else:
            print("Local PostgreSQL is already stopped.")
    elif action == "status":
        subprocess.run([str(bin_dir / "pg_ctl"), "-D", str(DATA), "status"], check=True)
    else:
        start(bin_dir, config)
        env = os.environ.copy()
        for field, name in (("host", "PGHOST"), ("port", "PGPORT"), ("dbname", "PGDATABASE"),
                            ("user", "PGUSER"), ("password", "PGPASSWORD"), ("sslmode", "PGSSLMODE")):
            env[name] = str(config[field])
        subprocess.run([str(bin_dir / "psql"), "--no-password"], env=env, check=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError, subprocess.CalledProcessError, psycopg.Error) as exc:
        # PostgreSQL errors can contain connection parameters; keep them out of console output.
        message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__ + "; check .local/postgres.log and local configuration."
        raise SystemExit(message) from None
