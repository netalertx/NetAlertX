#!/bin/sh
# This script recreates the database from schema code.
# Database location
NETALERTX_DB_FILE=${NETALERTX_DB:-/data/db}/app.db

#remove the old database
rm -f "${NETALERTX_DB_FILE}" "${NETALERTX_DB_FILE}-shm" "${NETALERTX_DB_FILE}-wal"

# Calculate script directory and schema path
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
# Path to the schema file (relative to script location: scripts/db_cleanup/ -> ../../server/db/schema/app.sql)
SCHEMA_FILE="${SCRIPT_DIR}/../../server/db/schema/app.sql"

if [ ! -f "${SCHEMA_FILE}" ]; then
    echo "Error: Schema file not found at ${SCHEMA_FILE}"
    exit 1
fi

# Import the database schema into the new database file
sqlite3 "${NETALERTX_DB_FILE}" < "${SCHEMA_FILE}"
