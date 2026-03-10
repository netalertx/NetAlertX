#!/bin/bash
# 36-override-individual-settings.sh - Applies environment variable overrides to app.conf

set -eu

# Ensure config exists
if [ ! -f "${NETALERTX_CONFIG}/app.conf" ]; then
    echo "[ENV] No config file found at ${NETALERTX_CONFIG}/app.conf — skipping overrides"
    exit 0
fi

if [ -n "${LOADED_PLUGINS:-}" ]; then
    echo "[ENV] Applying LOADED_PLUGINS override"
    value=$(printf '%s' "$LOADED_PLUGINS" | tr -d '\n\r')
    # declare delimiter for sed and escape it along with / and &
    delim='|'
    escaped=$(printf '%s\n' "$value" | sed "s/[\/${delim}&]/\\&/g")

    if grep -q '^LOADED_PLUGINS=' "${NETALERTX_CONFIG}/app.conf"; then
        # use same delimiter when substituting
        sed -i "s${delim}^LOADED_PLUGINS=.*${delim}LOADED_PLUGINS=${escaped}${delim}" "${NETALERTX_CONFIG}/app.conf"
    else
        echo "LOADED_PLUGINS=${value}" >> "${NETALERTX_CONFIG}/app.conf"
    fi
fi
