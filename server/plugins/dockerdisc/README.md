## Overview

`DOCKERDISC` enriches Docker **hosts** NetAlertX already knows about with
the list of containers running on them - image, Compose project/service,
network driver, and (for containers on a `macvlan`/`ipvlan` network) their
own MAC/IP.

It never creates the Docker **host** itself as a device - that must already
exist in NetAlertX before this plugin can attach anything to it. A
**container**, on the other hand, can optionally get its own device too:
opt in with `DOCKERDISC_CREATE_DEV` and a container on a `macvlan`/`ipvlan`
network (its own LAN-visible MAC) can create or confirm a device of its
own, parented to its host. A container without its own MAC
(`bridge`/overlay/etc.) never creates one, regardless of that setting -
there's no LAN-visible identity to create a device from.

Maintainer's mental model for this plugin: **Device = Docker host → List of
containers.** Every container found on a host shows up under that **host's
own** Device Details → Plugins → DOCKERDISC tab either way - opting a
container into its own device is additive, it doesn't remove it from the
host's list.

> [!TIP]
> Connects via a read-only [Docker Socket
> Proxy](https://github.com/Tecnativa/docker-socket-proxy) (e.g.
> `tecnativa/docker-socket-proxy`) - never mounts `/var/run/docker.sock`
> directly into the NetAlertX container.

### Why a Socket Proxy, and not `docker.sock` directly?

Mounting `/var/run/docker.sock` into a container gives that container the
same power as root on the host: anything that can reach the socket can,
for example, start a new `--privileged` container with the host
filesystem bind-mounted in - a standard, well-known way to escalate from
"container access" to "host root." It can't be scoped down to "read-only"
or "just these endpoints" - it's all or nothing.

That's a much bigger risk to accept for NetAlertX specifically than for a
small single-purpose tool: NetAlertX is a web UI, a GraphQL API, and
dozens of other plugins pulling in data from routers, DHCP leases, and
other external sources - a large attack surface. A vulnerability anywhere
in any of that would inherit full `docker.sock` access too, even though
this plugin itself only ever needs to read three things: the container
list, host info, and the network list.

The Socket Proxy sits between NetAlertX and the real socket and only
forwards the specific API paths this plugin actually needs
(`CONTAINERS=1`, `INFO=1`, `NETWORKS=1`) - everything else (exec, image
builds, volumes, secrets, any `POST` that creates/kills something) is
rejected by default. If NetAlertX is ever compromised, the blast radius
stops at "can list containers/networks," not "can root the host."

### Socket Proxy compose service

Add this as another service in the **same `docker-compose.yml` as
NetAlertX itself** - not a separate stack/file:

```yaml
services:
  netalertx:
    container_name: netalertx
    image: "ghcr.io/jokob-sk/netalertx"
    ... # same as you already have
    ...

  docker-socket-proxy:
    image: tecnativa/docker-socket-proxy:latest
    container_name: docker-socket-proxy
    environment:
      CONTAINERS: 1
      INFO: 1
      NETWORKS: 1
      POST: 0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
    # Only if netalertx uses network_mode: host - see note below
    # ports:
    #   - "127.0.0.1:2375:2375"
```

> [!NOTE]
> If your `netalertx` service uses `network_mode: host` (common, since ARP
> scanning needs a real host NIC), it won't resolve `docker-socket-proxy`
> by name - host networking means it isn't on the compose network at all.
> Fix: add `ports: ["127.0.0.1:2375:2375"]` to the proxy service above, and
> use `http://127.0.0.1:2375` as the Socket Proxy URL instead. Don't give
> the proxy `network_mode: host` too - that likely exposes it to the whole
> LAN instead of just the NAS.

Same file, on purpose:

- Compose puts every service in one file on the same default network
  automatically, so NetAlertX can reach it at `http://docker-socket-proxy:2375`
  for free - no extra `networks:` config, no port published to the LAN
  (nothing else needs to reach it). (`http://127.0.0.1:2375` only applies
  under the `network_mode: host` case above, not this default one - under
  default bridge networking each container has its own loopback, so
  `127.0.0.1` inside NetAlertX wouldn't reach the proxy container.)
- Its lifecycle naturally follows NetAlertX's - one `docker compose up`/
  `down` brings both up or down together, instead of a second stack to
  remember to manage separately.
- It's a dependency this plugin needs, not an unrelated service, so it
  belongs with NetAlertX conceptually as well as operationally.

(The only real reason to split it into its own stack is sharing one proxy
across several unrelated projects - e.g. Watchtower and NetAlertX both
reading from the same proxy instead of each running their own. Not needed
here.)

`POST: 0` is already the image's default; it's listed explicitly since
it's the setting that keeps this read-only - nothing here can
create/start/stop/kill anything.

### Quick setup guide

1. Add the Socket Proxy service above to NetAlertX's `docker-compose.yml`
   and bring it up (`docker compose up -d docker-socket-proxy`) - one per
   Docker host you want tracked, if you're tracking more than one.
2. In NetAlertX, add one entry per Docker host under **Docker hosts**
   (`DOCKERDISC_hosts`) with that proxy's URL (`http://127.0.0.1:2375`,
   `http://docker-socket-proxy:2375`, or whatever you named the service).
3. Make sure the Docker host itself already exists as a device in
   NetAlertX (it normally does, found via ARP/Nmap - Docker hosts have a
   real NIC on the LAN). If host-MAC auto-detection doesn't find it (see
   below), fill in its MAC manually in the same entry.

#### Required Settings

- When to run `DOCKERDISC_RUN`
- Docker hosts `DOCKERDISC_hosts` - at least one entry, each with:
  - Docker Socket Proxy URL `DOCKERDISC_SOCKET_PROXY_URL`
  - Docker Host MAC Address (Fallback) `DOCKERDISC_HOST_MAC` - optional if
    auto-detection works for that host

#### Optional Settings

- Create/confirm devices for containers with a real MAC
  `DOCKERDISC_CREATE_DEV` - off by default. A container without its own
  MAC (`bridge`/overlay/etc.) never creates a device either way; this only
  affects containers on a `macvlan`/`ipvlan` network.
- Allow updating existing devices from this plugin's data
  `DOCKERDISC_IMPORT_ON` - on by default. Turn off to make a run purely
  informational: no `CurrentScan` promotion at all, so a container's own
  already-existing device (found independently by ARP/Nmap) won't get its
  presence/IP/parent fields updated from this plugin either, regardless of
  `DOCKERDISC_CREATE_DEV`. The two settings are independent - one doesn't
  gate the other.

### Host MAC auto-detection

If `DOCKERDISC_HOST_MAC` is filled in, it's used immediately - no Socket
Proxy call at all. Deliberate trade-off: a MAC is stable, so there's
nothing to gain by re-confirming it via `/info` on every scheduled run,
but it also means a future MAC change (e.g. a replaced NIC) won't be
auto-detected while the field stays set.

Otherwise, the plugin calls the Socket Proxy's `GET /info` (Docker Engine
API) to read the daemon's hostname, then looks for a NetAlertX device
whose `devName` matches it. If either step fails - `/info` isn't reachable
(check the `INFO=1` permission), or no device's name matches - that host's
entry is skipped for the run (logged, not fatal to other hosts).

### Container listing

Every container on a host is listed, including `bridge`/overlay ones - not
only `macvlan`/`ipvlan` containers. What changes per container is only
whether it has a real LAN-visible identity to show:

- **Network Driver** (`watchedValue3`) is always populated.
- **Container MAC** (`watchedValue4`) and **IP** (`extra`) are populated
  only when the container has a `macvlan`/`ipvlan` network attached;
  otherwise they show `null`. A `bridge`-only container's own IP/MAC isn't
  LAN-visible, so there's nothing meaningful to show there - it still gets
  a row (image, Compose project/service, driver).
- If a container is attached to **more than one** `macvlan`/`ipvlan`
  network at the same time (uncommon, but possible - e.g. a dual-homed
  network appliance), the network whose *name* sorts first alphabetically
  is the one shown. This is a deliberate, deterministic tie-break, not an
  attempt to pick the "right" one - Docker doesn't expose any ordering or
  priority between a container's networks, so any rule here is arbitrary;
  what matters is that it's stable (the same container always reports the
  same MAC/IP) rather than depending on whatever order the Socket Proxy's
  JSON happens to return them in.

### Usage

- Head to **Settings** → **Docker discovery** to configure Docker hosts.
- Container details appear under each host's own **Device Details** →
  **Plugins** → **DOCKERDISC** tab.

### Notes

- The Docker host's own `devMac`/`devLastIP`/`devFirstConnection`/
  `devSourcePlugin`/`devCustomProps` are never touched - ARP/Nmap remain
  authoritative for the host's identity and discovery-source attribution.
  A container with its own macvlan/ipvlan MAC always maps to `CurrentScan`
  (`DOCKERDISC_IMPORT_ON` permitting) - with `DOCKERDISC_CREATE_DEV` on,
  it can originate a brand-new device; either way, if that MAC is already
  a device (found independently by ARP/Nmap, since it's LAN-visible), this
  plugin's row still confirms its presence and updates its
  `devLastIP`/`devParentMAC` on every run. Turn `DOCKERDISC_IMPORT_ON` off
  to skip all of that and keep this plugin purely informational (its
  `Plugins_Objects` listing still updates either way) - see [Plugin Import
  Behavior](../../../docs/PLUGINS_IMPORT_BEHAVIOR.md).
- Only Socket Proxy permissions required: `CONTAINERS=1` (list containers,
  their networks and labels), `INFO=1` (host-MAC auto-detection), and
  `NETWORKS=1` (network driver lookup - one batched `GET /networks` call
  per run for every unique network id seen, not one call per container).
  No write/exec permissions needed.
- Design history and open implementation questions in [issue #1721]
  (https://github.com/netalertx/NetAlertX/issues/1721).

- Version: 0.2.0
- Author: [mauricio-camayo](https://github.com/mauricio-camayo/)
- Release Date: `2026-09-18`
