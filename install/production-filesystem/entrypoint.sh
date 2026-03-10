#!/bin/bash

################################################################################
# NetAlertX Container Entrypoint
################################################################################
#
# Purpose: Main entrypoint script for NetAlertX Docker containers
#
# Responsibilities:
#   1. Display NetAlertX banner and container startup info
#   2. Run pre-startup health checks
#   3. Initialize required directories and log files
#   4. Start and monitor core services (crond, php-fpm, nginx, Python backend)
#   5. Handle service failures and graceful shutdown
#   6. Manage process signals (INT, TERM) for clean container termination
#
# Environment Variables:
#   - ENVIRONMENT: Container environment type (debian or alpine). If not "debian",
#                  crond scheduler service will be started.
#   - NETALERTX_DEBUG: If set to 1, services won't auto-shutdown on failure;
#                      container will wait for all to exit naturally (development mode).
#   - NETALERTX_PLUGINS_LOG: Directory path for plugin logs
#   - SYSTEM_SERVICES_RUN_LOG: Directory path for service runtime logs
#   - SYSTEM_SERVICES_RUN_TMP: Directory path for service temporary files
#   - LOG_DB_IS_LOCKED: File path for database lock status
#   - LOG_EXECUTION_QUEUE: File path for execution queue log
#
# Exit Codes:
#   - 0: Graceful shutdown (unlikely in production)
#   - 143: Caught signal (INT/TERM)
#   - Non-zero: Service failure status code
#
# Service Monitoring:
#   In production mode (NETALERTX_DEBUG != 1), if any service exits, all services
#   are terminated and the container exits with the failed service's status code.
#   This ensures container restart policies can properly reinitialize the stack.
#
################################################################################

# Allow direct command execution (e.g., `docker run -it netalertx bash`).
if [ "$#" -gt 0 ]; then
    case "$1" in
        bash|/bin/bash|sh|/bin/sh)
            exec "$@"
            ;;
    esac
fi

# If invoked directly (bypassing root-entrypoint), re-enter through it once for priming
# and privilege drop. Guard with ENTRYPOINT_PRIMED to avoid loops when root-entrypoint
# hands control back to this script.
if [ "${ENTRYPOINT_PRIMED:-0}" != "1" ] && [ "$(id -u)" -eq 0 ] && [ -x "/root-entrypoint.sh" ]; then
    >&2 cat <<'EOF'
ℹ️  NetAlertX startup: Running privilege check and path priming as ROOT.
    (On modern systems, privileges will be dropped to PUID after setup)
EOF
    export ENTRYPOINT_PRIMED=1
    exec /root-entrypoint.sh "$@"
fi

# Banner display
RED='\033[1;31m'
GREY='\033[90m'
RESET='\033[0m'
NAX='
 _   _      _    ___  _           _  __   __
| \ | |    | |  / _ \| |         | | \ \ / /
|  \| | ___| |_/ /_\ \ | ___ _ __| |_ \ V /
| .   |/ _ \ __|  _  | |/ _ \  __| __|/   \
| |\  |  __/ |_| | | | |  __/ |  | |_/ /^\ \
\_| \_/\___|\__\_| |_/_|\___|_|   \__\/   \/
'

printf "%b%s%b" "${RED}" "${NAX}" "${RESET}"
echo '   Network intruder and presence detector.
   https://netalertx.com

'
set -u
FAILED_STATUS=""
echo "Startup pre-checks"
for script in "${ENTRYPOINT_CHECKS}"/*; do
    if [ -n "${SKIP_TESTS:-}" ]; then
        echo "Skipping startup checks as SKIP_TESTS is set."
        break
    fi
    script_name=$(basename "$script" | sed 's/^[0-9]*-//;s/\.(sh|py)$//;s/-/ /g')
    echo "--> ${script_name} "
    if [ -n "${SKIP_STARTUP_CHECKS:-}" ] &&
       printf '%s' "${SKIP_STARTUP_CHECKS}" | grep -wFq -- "${script_name}"; then
        printf "%sskip%s\n" "${GREY}" "${RESET}"
        continue
    fi

    "$script"
    NETALERTX_DOCKER_ERROR_CHECK=$?

    if [ ${NETALERTX_DOCKER_ERROR_CHECK} -eq 1 ]; then
        >&2 printf "%s" "${RED}"
        >&2 cat <<EOF
══════════════════════════════════════════════════════════════════════════════
❌ NetAlertX startup aborted: critical failure in ${script_name}.
══════════════════════════════════════════════════════════════════════════════
EOF
        >&2 printf "%s" "${RESET}"

        FAILED_STATUS="1"
        if [ "${NETALERTX_DEBUG:-0}" -eq 1 ]; then
            echo "NETALERTX_DEBUG=1, continuing despite critical failure in ${script_name}."
        fi
    elif [ ${NETALERTX_DOCKER_ERROR_CHECK} -ne 0 ]; then
        # fail but continue checks so user can see all issues
        FAILED_STATUS="${NETALERTX_DOCKER_ERROR_CHECK}"
        echo "${script_name}: FAILED with ${FAILED_STATUS}"
        echo "Failure detected in: ${script}"
        # Continue to next check instead of exiting immediately
	fi
done


if [ -n "${FAILED_STATUS}" ]; then
    echo "Container startup checks failed with exit code ${FAILED_STATUS}."
    if [ "${NETALERTX_DEBUG:-0}" -eq 1 ]; then
        echo "NETALERTX_DEBUG=1, continuing despite failed pre-checks."
    else
        exit "${FAILED_STATUS}"
    fi
fi

# Set APP_CONF_OVERRIDE based on GRAPHQL_PORT if not already set
if [ -n "${GRAPHQL_PORT:-}" ] && [ -z "${APP_CONF_OVERRIDE:-}" ]; then
    export APP_CONF_OVERRIDE='{"GRAPHQL_PORT":"'"${GRAPHQL_PORT}"'"}'
    >&2 echo "APP_CONF_OVERRIDE detected (set from GRAPHQL_PORT)"
fi


# Exit after checks if in check-only mode (for testing)
if [ "${NETALERTX_CHECK_ONLY:-0}" -eq 1 ]; then
	exit 0
fi

# Update vendor data (MAC address OUI database) in the background
# This happens concurrently with service startup to avoid blocking container readiness
bash "${SYSTEM_SERVICES_SCRIPTS}/update_vendors.sh" &



# Service management state variables
SERVICES=""                 # Space-separated list of active services in format "pid:name"
FAILED_NAME=""              # Name of service that failed (used for error reporting)

################################################################################
# is_pid_active() - Check if a process is alive and not in zombie/dead state
################################################################################
# Arguments:
#   $1: Process ID to check
# Returns:
#   0 (success): Process is alive and healthy
#   1 (failure): Process is dead, zombie, or PID is empty
################################################################################
is_pid_active() {
    pid="$1"
    [ -z "${pid}" ] && return 1

    if ! kill -0 "${pid}" 2>/dev/null; then
        return 1
    fi

    if [ -r "/proc/${pid}/status" ]; then
        state_line=$(grep '^State:' "/proc/${pid}/status" 2>/dev/null || true)
        case "${state_line}" in
            *"(zombie)"*|*"(dead)"*)
                return 1
                ;;
        esac
    fi

    return 0
}

add_service() {
    # Start a new service script and track it for monitoring
    # Arguments:
    #   $1: Path to service startup script (e.g., /services/start-backend.sh)
    #   $2: Human-readable service name (for logging and error reporting)
    script="$1"
    name="$2"
    "$script" &
    pid=$!
    SERVICES="${SERVICES} ${pid}:${name}"
}

################################################################################
# remove_service() - Remove a service from the active services list
################################################################################
# Arguments:
#   $1: Process ID to remove
# Updates: SERVICES variable to exclude the specified PID
################################################################################
remove_service() {
    target_pid="$1"
    updated=""
    for entry in ${SERVICES}; do
        pid="${entry%%:*}"
        [ -z "${pid}" ] && continue
        [ "${pid}" = "${target_pid}" ] && continue
        updated="${updated} ${entry}"
    done
    SERVICES="${updated}"
}

################################################################################
# shutdown_services() - Gracefully stop all active services
################################################################################
# Process:
#   1. Send SIGTERM to all active services (time to clean up)
#   2. Wait for all services to fully terminate
# Notes:
#   - Tolerates services that are already dead
#   - Uses 'wait' to reap zombie processes
################################################################################
shutdown_services() {
    for entry in ${SERVICES}; do
        pid="${entry%%:*}"
        [ -z "${pid}" ] && continue
        if is_pid_active "${pid}"; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
    for entry in ${SERVICES}; do
        pid="${entry%%:*}"
        [ -z "${pid}" ] && continue
        wait "${pid}" 2>/dev/null || true
    done
    echo "All services stopped."
}

################################################################################
# handle_exit() - Terminate all services and exit container
################################################################################
# Process:
#   1. Log failure information if a service exited abnormally
#   2. Shut down all remaining services gracefully
#   3. Exit container with recorded status code
# Note: Used when a monitored service fails or signal is caught
################################################################################
handle_exit() {
    if [ -n "${FAILED_NAME}" ]; then
        echo "Service ${FAILED_NAME} exited with status ${FAILED_STATUS}."
    fi
    shutdown_services
    exit "${FAILED_STATUS}"
}

################################################################################
# on_signal() - Handle container signals (INT, TERM) for graceful shutdown
################################################################################
# Signals handled: SIGINT (Ctrl+C), SIGTERM (docker stop)
# Process:
#   1. Set exit status to 143 (128 + 15, standard SIGTERM code)
#   2. Trigger full shutdown sequence
# Note: Registered via 'trap' command below
################################################################################
on_signal() {
    echo "Caught signal, shutting down services..."
    FAILED_NAME="signal"
    FAILED_STATUS=143
    handle_exit
}

# Register signal handlers for graceful shutdown
trap on_signal INT TERM



# Start services based on environment configuration

# Only start crond scheduler on Alpine (non-Debian) environments
# Debian typically uses systemd or other schedulers
if [ "${ENVIRONMENT:-}" ] && [ "${ENVIRONMENT:-}" != "debian" ]; then
    add_service "/services/start-cron.sh" "supercronic"
fi

# Start core frontend and backend services
# Order: web server, application server, then Python backend
add_service "${SYSTEM_SERVICES}/start-php-fpm.sh" "php-fpm83"
add_service "${SYSTEM_SERVICES}/start-nginx.sh" "nginx"
add_service "${SYSTEM_SERVICES}/start-backend.sh" "python3"

################################################################################
# Service Monitoring Loop (Production Mode)
################################################################################
# Behavior depends on NETALERTX_DEBUG setting:
#   - DEBUG OFF (production): Any service failure triggers full container restart
#   - DEBUG ON: Services can fail individually; container waits for natural exit
#
# Loop Process:
#   1. Check each active service every 10 seconds
#   2. If service is not active, wait for it and capture exit status
#   3. Log failure and terminate all other services
#   4. Exit container with failed service's status code
#   5. This enables Docker restart policies to reinitialize the stack
################################################################################
while [ -n "${SERVICES}" ]; do
    for entry in ${SERVICES}; do
        pid="${entry%%:*}"
        name="${entry#*:}"
        [ -z "${pid}" ] && continue
        if ! is_pid_active "${pid}"; then
            wait "${pid}" 2>/dev/null
            status=$?

            # Handle intentional backend restart
            if [ "${name}" = "python3" ] && [ -f "/tmp/backend_restart_pending" ]; then
                echo "🔄 Backend restart requested via marker file."
                rm -f "/tmp/backend_restart_pending"
                remove_service "${pid}"
                add_service "${SYSTEM_SERVICES}/start-backend.sh" "python3"
                continue
            fi

            FAILED_STATUS=$status
            FAILED_NAME="${name}"
            remove_service "${pid}"

            if [ "${NETALERTX_DEBUG:-0}" -eq 1 ]; then
                echo "⚠️ Service ${name} exited with status ${status}. Debug mode active - continuing."
            else
                handle_exit
            fi
        fi

    done
    sleep 10
done

# If we exit the loop with no service failures, set status to 1 (error)
# This should not happen in normal operation
if [ "${FAILED_STATUS}" -eq 0 ] && [ "${FAILED_NAME}" != "signal" ]; then
    FAILED_STATUS=1
fi