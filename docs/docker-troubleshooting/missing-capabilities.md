# Missing Network Capabilities

## Issue Description

Raw network capabilities (NET_RAW, NET_ADMIN, NET_BIND_SERVICE) are missing. Tools that rely on these capabilities (e.g., nmap -sS, arp-scan, nbtscan) will not function.

## Security Ramifications

Network scanning and monitoring requires low-level network access that these capabilities provide. Without them, the application cannot perform essential functions like ARP scanning, port scanning, or passive network discovery, severely limiting its effectiveness.

## Why You're Seeing This Issue

This occurs when the container doesn't have the necessary Linux capabilities granted. Docker containers run with limited capabilities by default, and network monitoring tools need elevated network privileges.

## Supported Capabilities

NetAlertX supports exactly these capabilities; anything beyond them triggers the [excessive capabilities](excessive-capabilities.md) warning.

| Capability | Needed for | Required |
|------------|-----------|----------|
| `NET_RAW` | Raw socket operations by the scanners | Yes - the image's Python binary fails to start without it |
| `NET_ADMIN` | ARP scanning, and applying [ARP sysctls](arp-flux-sysctls.md) at runtime with host networking | Yes - the image's Python binary fails to start without it |
| `NET_BIND_SERVICE` | `nbtscan` binding to privileged UDP port 137 | Recommended - without it NetBIOS discovery of legacy devices is less accurate and a startup warning is logged |
| `CHOWN` | Root priming of `/data` and `/tmp` ownership at startup | Only with `cap_drop: [ALL]` - without it ownership is not changed and a warning is logged (see below) |
| `SETUID`, `SETGID` | Dropping from root to `PUID:PGID` at startup | Only when starting as root with `cap_drop: [ALL]` - without them the container keeps running as root ([details](PUID_PGID_SECURITY.md)) |

The image sets `+eip` file capabilities on `nmap`, `arp-scan`, `iw`, `traceroute` and the Python interpreter (`NET_RAW`, `NET_ADMIN`), and on `nbtscan` (also `NET_BIND_SERVICE`). A binary with file capabilities fails with "Operation not permitted" if those capabilities are not in the container's bounding set, which is why the `cap_add` entries below are required.

> [!NOTE]
> Because the Python interpreter carries file capabilities, the server process runs non-dumpable, and the kernel makes its `/proc/self/io` readable only by root. When NetAlertX runs as a non-root user without elevated privileges (the default), the **System Info → Performance** IO charts can therefore read `0`, while CPU, memory, and scan duration stay accurate. Running as root or with `--privileged` does not have this limitation. See [Performance](../PERFORMANCE.md#tracking-netalertxs-own-resource-usage-over-time).

## How to Correct the Issue

Add the required capabilities to your container:

- In docker-compose.yml:
  ```yaml
  cap_add:
    - NET_RAW
    - NET_ADMIN
    - NET_BIND_SERVICE
  ```
- For docker run: `--cap-add=NET_RAW --cap-add=NET_ADMIN --cap-add=NET_BIND_SERVICE`

## Additional Resources

Docker Compose setup can be complex. We recommend starting with the default docker-compose.yml as a base and modifying it incrementally.

For detailed Docker Compose configuration guidance, see: [DOCKER_COMPOSE.md](https://docs.netalertx.com/DOCKER_COMPOSE)

## CAP_CHOWN required when cap_drop: [ALL]

When you start NetAlertX with `cap_drop: [ALL]`, the container loses `CAP_CHOWN`. The root priming step needs `CAP_CHOWN` to adjust ownership of `/data` and `/tmp` before dropping privileges to `PUID:PGID`. Without it, startup fails with a fatal `failed to chown` message and exits.

To fix:
- Add `CHOWN` back in `cap_add` when you also set `cap_drop: [ALL]`:

  ```yaml
  cap_drop:
    - ALL
  cap_add:
    - CHOWN
  ```

- Or pre-chown the mounted host paths to your target `PUID:PGID` so the priming step does not need the capability.

If you harden capabilities further, expect priming to fail until you restore the minimum set needed for ownership changes.