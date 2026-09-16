#!/usr/bin/env sh
set -e

# DATABASE_URL wins when set, which is how managed hosts supply the database.
# POSTGRES_HOST/PORT is the Docker Compose path.
target=$(python -c "
import os
from urllib.parse import urlparse

url = os.environ.get('DATABASE_URL')
if url:
    parsed = urlparse(url)
    print(parsed.hostname or 'db', parsed.port or 5432)
else:
    print(os.environ.get('POSTGRES_HOST', 'db'), os.environ.get('POSTGRES_PORT', '5432'))
")
host=${target% *}
port=${target#* }
attempts=${DB_WAIT_ATTEMPTS:-60}

echo "Waiting for Postgres at $host:$port..."
tries=0
until python -c "
import socket, sys
sock = socket.socket()
sock.settimeout(2)
try:
    sock.connect(('$host', int('$port')))
except OSError:
    sys.exit(1)
finally:
    sock.close()
"; do
  tries=$((tries + 1))
  if [ "$tries" -ge "$attempts" ]; then
    echo "Cannot reach Postgres at $host:$port after $attempts tries. Check DATABASE_URL." >&2
    exit 1
  fi
  sleep 1
done

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API..."
exec "$@"
