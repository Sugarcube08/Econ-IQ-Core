#!/bin/bash
set -e

# Export default environment variables for local single-container execution
export APP_NAME="Econiq Core Platform"
export APP_ENV="development"
export DEBUG="True"
export LOG_LEVEL="DEBUG"
export HOST="0.0.0.0"
export PORT="${PORT:-8000}"
export WORKERS="1"

# Database Configuration (pointing to localhost since Postgres/Redis run inside this container)
export POSTGRES_URL="${POSTGRES_URL:-postgresql+asyncpg://sugarcube:SugarCube#08@localhost:5432/ir_econiq}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# JWT configuration with default working development keys
export JWT_ALGORITHM="EdDSA"
export JWT_PRIVATE_KEY="${JWT_PRIVATE_KEY:-"-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIJIY1WfCIBtAbseRVQfeatR8z6542W4AiWGwAwjMWOWX\n-----END PRIVATE KEY-----"}"
export JWT_PUBLIC_KEY="${JWT_PUBLIC_KEY:-"-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAm+DnEa2VujJ8N4ZhZI5e1PkIcYUJG/k1XrNVyZ6MEEk=\n-----END PUBLIC KEY-----"}"

# Worker configuration
export BACKGROUND_PROCESSING_ENABLED="True"
export STARTUP_MODE="full"
export OTP_PEPPER="9cc37a23d6e3613814f4a72b148d7c4a12a54d7e74bd2a3d7e61265790a84b15"
export API_KEY_PEPPER="5b8f92f2c1a3c849429e51cb9689d07cb75835042c75ce2b7a5b9ee76cb4f96e"
export REFRESH_TOKEN_PEPPER="931d0e52352e3684136fdec0028180c23a78d862725602f191914c9591df2950"

# Check if we should use local PostgreSQL
if [[ "$POSTGRES_URL" == *"localhost"* || "$POSTGRES_URL" == *"127.0.0.1"* ]]; then
  echo "=== Handling PostgreSQL Persistent Volume Mounts ==="
  PG_VERSION=$(pg_conftool --version 2>/dev/null || echo "15")
  PG_DATA_DIR="/var/lib/postgresql/$PG_VERSION/main"
  
  if [ ! -d "$PG_DATA_DIR" ] || [ -z "$(ls -A $PG_DATA_DIR 2>/dev/null)" ]; then
    echo "=== Initializing empty PostgreSQL cluster directory ==="
    mkdir -p "$PG_DATA_DIR"
    chown -R postgres:postgres /var/lib/postgresql
    # Create the cluster using pg_createcluster
    pg_createcluster "$PG_VERSION" main || true
  fi

  echo "=== Starting Local PostgreSQL ==="
  service postgresql start

  # Wait for PostgreSQL to be ready
  until pg_isready -h localhost -U postgres; do
    echo "Waiting for PostgreSQL to start..."
    sleep 1
  done

  echo "=== Configuring PostgreSQL database ==="
  # Create user and db if not exists
  su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='sugarcube'\" | grep -q 1 || psql -c \"CREATE USER sugarcube WITH PASSWORD 'SugarCube#08' SUPERUSER;\""
  su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='ir_econiq'\" | grep -q 1 || psql -c \"CREATE DATABASE ir_econiq OWNER sugarcube;\""
fi

# Check if we should use local Redis
if [[ "$REDIS_URL" == *"localhost"* || "$REDIS_URL" == *"127.0.0.1"* ]]; then
  echo "=== Starting Local Redis ==="
  service redis-server start

  # Wait for Redis to be ready
  until redis-cli ping | grep -q PONG; do
    echo "Waiting for Redis to start..."
    sleep 1
  done
fi

echo "=== Initializing Database Schema ==="
python -c '
import asyncio
from core.storage.postgres import Base, engine, AsyncSessionLocal
from core.ingestion.sync_pipeline import SyncPipeline

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        pipeline = SyncPipeline()
        await pipeline.upgrade_raw_tables_schema(session)
    print("Database schema successfully initialized.")

asyncio.run(init())
'

echo "=== Seeding Demo Customers ==="
python seed_demo_customers.py || echo "Warning: Demo customer seeding failed or already exists"

echo "=== Starting Services via Supervisor ==="
exec supervisord -c /etc/supervisor/conf.d/econiq.conf
