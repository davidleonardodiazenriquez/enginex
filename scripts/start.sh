#!/bin/sh
set -eu
python manage.py process_contracts --loop &
worker_pid=$!
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - &
web_pid=$!
trap 'kill "$worker_pid" "$web_pid" 2>/dev/null || true; wait; exit 0' TERM INT
# Restart the replica if either required process stops.
while kill -0 "$worker_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do sleep 3 & wait $!; done
kill "$worker_pid" "$web_pid" 2>/dev/null || true
wait || true
exit 1
