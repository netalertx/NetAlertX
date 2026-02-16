#!/bin/sh
# Ensures the database exists, or creates a new one on first run.
# Intended to run only at initial startup.

# Fix permissions if DB directory exists but is unreadable
if [ -d "${NETALERTX_DB}" ]; then
    chmod u+rwX "${NETALERTX_DB}" 2>/dev/null || true
fi
chmod u+rw "${NETALERTX_DB_FILE}" 2>/dev/null || true

set -eu

CYAN=$(printf '\033[1;36m')
RED=$(printf '\033[1;31m')
RESET=$(printf '\033[0m')

# Ensure DB folder exists
if [ ! -d "${NETALERTX_DB}" ]; then
    if ! mkdir -p "${NETALERTX_DB}"; then
        >&2 printf "%s" "${RED}"
        >&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
❌  Error creating DB folder in: ${NETALERTX_DB}

A database directory is required for proper operation, however there appear to be
insufficient permissions on this mount or it is otherwise inaccessible.

More info: https://docs.netalertx.com/FILE_PERMISSIONS
══════════════════════════════════════════════════════════════════════════════
EOF
        >&2 printf "%s" "${RESET}"
        exit 1
    fi
    chmod 700 "${NETALERTX_DB}" 2>/dev/null || true
fi

# Fresh rebuild requested
if [ "${ALWAYS_FRESH_INSTALL:-false}" = "true" ] && [ -f "${NETALERTX_DB_FILE}" ]; then
    >&2 echo "INFO: ALWAYS_FRESH_INSTALL enabled — removing existing database."
    rm -f "${NETALERTX_DB_FILE}" "${NETALERTX_DB_FILE}-shm" "${NETALERTX_DB_FILE}-wal"
fi

# If file exists now, nothing to do
if [ -f "${NETALERTX_DB_FILE}" ]; then
    exit 0
fi

>&2 printf "%s" "${CYAN}"
>&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
🆕  First run detected — building initial database at: ${NETALERTX_DB_FILE}

    Do not interrupt this step. When complete, consider backing up the fresh
    DB before onboarding sensitive or critical networks.
══════════════════════════════════════════════════════════════════════════════
EOF
>&2 printf "%s" "${RESET}"


# Write all text to db file until we see "end-of-database-schema"
sqlite3 "${NETALERTX_DB_FILE}" < "${NETALERTX_SERVER}/db/schema/app.sql"

database_creation_status=$?

if [ $database_creation_status -ne 0 ]; then
  RED=$(printf '\033[1;31m')
  RESET=$(printf '\033[0m')
  >&2 printf "%s" "${RED}"
  >&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
❌  CRITICAL: Database schema creation failed for ${NETALERTX_DB_FILE}.

    NetAlertX cannot start without a properly initialized database. This
    failure typically indicates:

    * Insufficient disk space or write permissions in the database directory
    * Corrupted or inaccessible SQLite installation
    * File system issues preventing database file creation

    Check the logs for detailed SQLite error messages. Ensure the container
    has write access to the database path and adequate storage space.
══════════════════════════════════════════════════════════════════════════════
EOF
  >&2 printf "%s" "${RESET}"
  exit 1
fi