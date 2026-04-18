#!/bin/bash
#
# run_tests_in_docker_environment.sh
#
# This script automates the entire process of testing the application
# within its intended, privileged devcontainer environment. It is
# idempotent and can be run repeatedly.
#

set -e

# --- 1. Regenerate Devcontainer Dockerfile ---
echo "--- Regenerating .devcontainer/Dockerfile from source ---"
if [ -f ".devcontainer/scripts/generate-configs.sh" ]; then
    /bin/bash .devcontainer/scripts/generate-configs.sh
else
    echo "ERROR: generate-configs.sh not found. Aborting."
    exit 1
fi
echo "Development $(git rev-parse --short=8 HEAD)" |  tee ".VERSION" >/dev/null
date +%s > front/buildtimestamp.txt


# --- 2. Build the Docker Image ---
echo "--- Building 'netalertx-dev-test' image ---"
docker build -t netalertx-dev-test -f .devcontainer/Dockerfile . --target netalertx-devcontainer

# --- 3. Cleanup Old Containers ---
echo "--- Cleaning up previous container instance (if any) ---"
docker stop netalertx-test-container >/dev/null 2>&1 || true
docker rm netalertx-test-container >/dev/null 2>&1 || true

# --- 4. Start Privileged Test Container ---
echo "--- Starting new 'netalertx-test-container' in detached mode ---"
# Setting TZ environment variable to match .env file
docker run -d --name netalertx-test-container \
  -e TZ=Europe/Paris \
  --cap-add SYS_ADMIN \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  --cap-add NET_BIND_SERVICE \
  --security-opt apparmor=unconfined \
  --add-host=host.docker.internal:host-gateway \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)":/workspaces/NetAlertX \
  netalertx-dev-test

# --- 5. Install Python test dependencies ---
echo "--- Installing Python test dependencies into venv ---"
docker exec netalertx-test-container pip3 install --break-system-packages pytest docker debugpy selenium ldap3

# --- 6. Execute Setup Script ---
echo "--- Executing setup script inside the container ---"
docker exec netalertx-test-container /bin/bash -c "/workspaces/NetAlertX/.devcontainer/scripts/setup.sh"

# --- 7. Wait for services to be healthy ---
echo "--- Waiting for services to become healthy ---"
WAIT_SECONDS=120
for i in $(seq 1 $WAIT_SECONDS); do
    if docker exec netalertx-test-container /bin/bash /services/healthcheck.sh; then
        echo "--- Services are healthy! ---"
        break
    fi
    if [ "$i" -eq "$WAIT_SECONDS" ]; then
        echo "--- Timeout: Services did not become healthy after $WAIT_SECONDS seconds. ---"
        docker logs netalertx-test-container
        exit 1
    fi
    echo "    ... waiting ($i/$WAIT_SECONDS)"
    sleep 1
done


# --- 8. Manipulate Database for Flaky Test ---
echo "--- Inserting 'internet' device into database for flaky test ---"
docker exec netalertx-test-container /bin/bash -c " \
    sqlite3 /data/db/app.db \"INSERT OR IGNORE INTO Devices (devMac, devFirstConnection, devLastConnection, devLastIP, devName) VALUES ('internet', DATETIME('now'), DATETIME('now'), '0.0.0.0', 'Internet Gateway');\" \
"

# --- 9. Execute Tests ---
echo "--- Executing tests inside the container ---"
docker exec netalertx-test-container /bin/bash -c " \
    cd /workspaces/NetAlertX && pytest -m 'not (docker or compose or feature_complete)' --cache-clear -o cache_dir=/tmp/.pytest_cache; \
"

# --- 10. Final Teardown ---
echo "--- Tearing down the test container ---"
docker stop netalertx-test-container
docker rm netalertx-test-container

echo "--- Test run complete! ---"
