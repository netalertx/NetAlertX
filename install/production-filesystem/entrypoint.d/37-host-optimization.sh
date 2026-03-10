#!/bin/sh

# 37-host-optimization.sh: Detect ARP flux sysctl configuration.
#
# This script does not change host/kernel settings.

YELLOW=$(printf '\033[1;33m')
RESET=$(printf '\033[0m')

failed=0

[ "$(sysctl -n net.ipv4.conf.all.arp_ignore 2>/dev/null || echo unknown)" = "1" ] || failed=1
[ "$(sysctl -n net.ipv4.conf.all.arp_announce 2>/dev/null || echo unknown)" = "2" ] || failed=1

if [ "$failed" -eq 1 ]; then
    >&2 printf "%s" "${YELLOW}"
    >&2 cat <<'EOF'
══════════════════════════════════════════════════════════════════════════════
⚠️  WARNING: ARP flux sysctls are not set.

    Expected values:
      net.ipv4.conf.all.arp_ignore=1
      net.ipv4.conf.all.arp_announce=2

    Detection accuracy may be reduced until configured.

    See: https://docs.netalertx.com/docker-troubleshooting/arp-flux-sysctls/
══════════════════════════════════════════════════════════════════════════════
EOF
    >&2 printf "%s" "${RESET}"
fi
