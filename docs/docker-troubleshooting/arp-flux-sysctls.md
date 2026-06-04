# ARP Flux Sysctls Not Set

## Issue Description

NetAlertX detected that ARP flux protection sysctls are not set as expected:

- `net.ipv4.conf.all.arp_ignore=1`
- `net.ipv4.conf.all.arp_announce=2`

## Security Ramifications

This is not a direct container breakout risk, but detection quality can degrade:

- Incorrect IP/MAC associations
- Device state flapping
- Unreliable topology or presence data

## Why You're Seeing This Issue

The running environment does not provide the expected kernel sysctl values. This is common in Docker setups where sysctls were not explicitly configured.

## How to Correct the Issue

### Option A: Via Docker (Standard Bridge Networking or `network_mode: host` with `NET_ADMIN`)

If you are using standard bridged networking, or `network_mode: host` and the container is granted the `NET_ADMIN` capability (as is the default recommendation), set these sysctls at container runtime.

- In `docker-compose.yml` (preferred):
  ```yaml
  services:
    netalertx:
      sysctls:
        net.ipv4.conf.all.arp_ignore: 1
        net.ipv4.conf.all.arp_announce: 2
  ```

- For `docker run`:
  ```bash
  docker run \
    --sysctl net.ipv4.conf.all.arp_ignore=1 \
    --sysctl net.ipv4.conf.all.arp_announce=2 \
    ghcr.io/netalertx/netalertx:latest
  ```
  
> **Note:** Setting `net.ipv4.conf.all.arp_ignore` and `net.ipv4.conf.all.arp_announce` may fail with "operation not permitted" unless the container is run with elevated privileges. To resolve this, you can:
> - Use `--privileged` with `docker run`.
> - Use the more restrictive `--cap-add=NET_ADMIN` (or `cap_add: [NET_ADMIN]` in `docker-compose` service definitions) to allow the sysctls to be applied at runtime.

### Option B: Via Host OS (Fallback for `network_mode: host`)

If you are running the container with `network_mode: host` and cannot grant the `NET_ADMIN` capability, or if your container runtime environment explicitly blocks sysctl overrides, applying these settings via the container configuration will fail. Attempting to do so without sufficient privileges typically results in an OCI runtime error: `sysctl "net.ipv4.conf.all.arp_announce" not allowed in host network namespace`.

In this scenario, you must apply the settings directly on your host operating system:

1. **Remove** the `sysctls` section from your `docker-compose.yml`.
2. **Apply** on the host immediately:
   ```bash
   sudo sysctl -w net.ipv4.conf.all.arp_ignore=1
   sudo sysctl -w net.ipv4.conf.all.arp_announce=2
   ```
3. **Make persistent** by adding the following lines to `/etc/sysctl.conf` on the host:
   ```text
   net.ipv4.conf.all.arp_ignore=1
   net.ipv4.conf.all.arp_announce=2
   ```

## Additional Resources

For broader Docker Compose guidance, see:

- [DOCKER_COMPOSE.md](https://docs.netalertx.com/DOCKER_COMPOSE)
