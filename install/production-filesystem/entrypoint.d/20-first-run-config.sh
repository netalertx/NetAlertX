#!/bin/bash
# first-run-check.sh - Checks and initializes configuration files on first run

# Fix permissions if config directory exists but is unreadable
if [ -d "${NETALERTX_CONFIG}" ]; then
    chmod u+rwX "${NETALERTX_CONFIG}" 2>/dev/null || true
fi
chmod u+rw "${NETALERTX_CONFIG}/app.conf" 2>/dev/null || true

### Helper function to set the SCAN_SUBNETS based on active interfaces during first run
get_scan_subnets() {
    _list=""
    while read -r _cidr _iface; do
        [[ "$_iface" =~ ^(lo|docker|veth) ]] && continue
        
        _net=$(ipcalc -n "$_cidr" | awk -F= '{print $2}')
        _mask=$(echo "$_cidr" | cut -d/ -f2)
        _entry="${_net}/${_mask} --interface=${_iface}"

        if [ -z "$_list" ]; then
            _list="'$_entry'"
        else
            _list="$_list,'$_entry'"
        fi
    done < <(ip -o -4 addr show scope global | awk '{print $4, $2}')

    [ -z "$_list" ] && printf "['--localnet']" || printf "[%s]" "$_list"
}

set -eu

CYAN=$(printf '\033[1;36m')
RED=$(printf '\033[1;31m')
RESET=$(printf '\033[0m')

# Ensure config folder exists
if [ ! -d "${NETALERTX_CONFIG}" ]; then
    if ! mkdir -p "${NETALERTX_CONFIG}"; then
        >&2 printf "%s" "${RED}"
        >&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
❌  Error creating config folder in: ${NETALERTX_CONFIG}

A config directory is required for proper operation, however there appear to be
insufficient permissions on this mount or it is otherwise inaccessible.

More info: https://docs.netalertx.com/FILE_PERMISSIONS
══════════════════════════════════════════════════════════════════════════════
EOF
        >&2 printf "%s" "${RESET}"
        exit 1
    fi
    chmod 700 "${NETALERTX_CONFIG}" 2>/dev/null || true
fi

# Fresh rebuild requested
if [ "${ALWAYS_FRESH_INSTALL:-false}" = "true" ] && [ -e "${NETALERTX_CONFIG}/app.conf" ]; then
    >&2 echo "INFO: ALWAYS_FRESH_INSTALL enabled — removing existing config."
    rm -rf "${NETALERTX_CONFIG:?}"/*
fi

# Check for app.conf and deploy if required
if [ ! -f "${NETALERTX_CONFIG}/app.conf" ]; then
    install -m 600 /app/back/app.conf "${NETALERTX_CONFIG}/app.conf" || {
        >&2 echo "ERROR: Failed to deploy default config to ${NETALERTX_CONFIG}/app.conf"
        exit 2
    }
	# Generate the dynamic subnet list
    SCAN_LIST=$(get_scan_subnets)

    # Inject into the newly deployed config
    sed -i "s|^SCAN_SUBNETS=.*|SCAN_SUBNETS=$SCAN_LIST|" "${NETALERTX_CONFIG}/app.conf" ||true

    >&2 printf "%s" "${CYAN}"
    >&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
🆕  First run detected. Default configuration written to ${NETALERTX_CONFIG}/app.conf.

    Review your settings in the UI or edit the file directly before trusting
    this instance in production.
══════════════════════════════════════════════════════════════════════════════
EOF
    >&2 printf "%s" "${RESET}"
fi

