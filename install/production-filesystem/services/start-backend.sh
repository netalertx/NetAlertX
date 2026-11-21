#!/bin/bash

cd "${NETALERTX_APP}" || exit 1

# The sweep below matches by process NAME (killall python3), not by a
# specific PID - correct for a fresh container boot (clears any stale
# lingering backend), but wrong for a recovery restart after an unexpected
# crash: the crashed PID is already gone, and a blanket sweep would also
# kill any unrelated python3 process in the container, such as a
# currently-running plugin subprocess that has nothing to do with the
# crashed backend. entrypoint.sh's recovery call sites set
# NETALERTX_SKIP_BACKEND_KILL_SWEEP=1 to skip this sweep entirely.
if [ "${NETALERTX_SKIP_BACKEND_KILL_SWEEP:-0}" != "1" ]; then
	max_attempts=50  # 10 seconds total (50 * 0.2s)
	attempt=0
	while pgrep -x python3 >/dev/null && [ $attempt -lt $max_attempts ]; do
		killall -TERM python3 &>/dev/null
		sleep 0.2
		((attempt++))
	done
	# Force kill if graceful shutdown failed
	killall -KILL python3 &>/dev/null
fi

read -ra EXTRA_PARAMS < <(cat /services/config/python/backend-extra-launch-parameters 2>/dev/null)
echo "Starting python3 ${EXTRA_PARAMS[*]} -m server (stdout+stderr merged)"
# Append to LOG_STDERR rather than leaving this on whatever stdout this
# script inherited: when entrypoint.sh is invoked via `docker exec` (the
# devcontainer/CI test path, not production's container-is-PID-1 path),
# that inherited stdout has no reliable reader once the exec session that
# started it returns - a crash traceback here previously had nowhere
# visible to go. `exec` (not a pipe) keeps this process's PID stable for
# entrypoint.sh's own PID-based monitoring.
exec python3 "${EXTRA_PARAMS[@]}" -m server >>"${LOG_STDERR:-/tmp/log/stderr.log}" 2>&1
