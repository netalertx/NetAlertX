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

Set these sysctls at container runtime.

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

## Additional Resources

For broader Docker Compose guidance, see:

- [DOCKER_COMPOSE.md](https://docs.netalertx.com/DOCKER_COMPOSE)
