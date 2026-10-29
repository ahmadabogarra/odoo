#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${ODOO_DB_PASSWORD:?ODOO_DB_PASSWORD is required}"

PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-railway}"
ODOO_DB_USER="${ODOO_DB_USER:-odoo}"

export PGPASSWORD

ROLE_EXISTS="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'odoo';" | tr -d '[:space:]')"
if [ "$ROLE_EXISTS" != "1" ]; then
    createuser \
        -h "$PGHOST" \
        -p "$PGPORT" \
        -U "$PGUSER" \
        --createdb \
        --no-superuser \
        --no-createrole \
        odoo
fi

psql \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d "$PGDATABASE" \
    -v ON_ERROR_STOP=1 \
    -v role_password="$ODOO_DB_PASSWORD" <<'SQL'
SELECT format('ALTER ROLE odoo WITH LOGIN CREATEDB PASSWORD %L', :'role_password') \gexec
SQL

unset PGPASSWORD

mkdir -p /var/lib/odoo
chown -R odoo:odoo /var/lib/odoo

exec gosu odoo ./odoo-bin \
    --http-interface=0.0.0.0 \
    --http-port="${PORT:-8069}" \
    --proxy-mode \
    --data-dir=/var/lib/odoo \
    --db_host="$PGHOST" \
    --db_port="$PGPORT" \
    --db_user="$ODOO_DB_USER" \
    --db_password="$ODOO_DB_PASSWORD"
