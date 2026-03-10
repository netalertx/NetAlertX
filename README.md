[![Docker Size](https://img.shields.io/docker/image-size/jokobsk/netalertx?label=Size&logo=Docker&color=0aa8d2&logoColor=fff&style=for-the-badge)](https://hub.docker.com/r/jokobsk/netalertx)
[![Docker Pulls](https://img.shields.io/docker/pulls/jokobsk/netalertx?label=Pulls&logo=docker&color=0aa8d2&logoColor=fff&style=for-the-badge)](https://hub.docker.com/r/jokobsk/netalertx)
[![GitHub Release](https://img.shields.io/github/v/release/netalertx/NetAlertX?color=0aa8d2&logoColor=fff&logo=GitHub&style=for-the-badge)](https://github.com/netalertx/NetAlertX/releases)
[![Discord](https://img.shields.io/discord/1274490466481602755?color=0aa8d2&logoColor=fff&logo=Discord&style=for-the-badge)](https://discord.gg/NczTUTWyRr)
[![Home Assistant](https://img.shields.io/badge/Repo-blue?logo=home-assistant&style=for-the-badge&color=0aa8d2&logoColor=fff&label=Add)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Falexbelgium%2Fhassio-addons)

# NetAlertX - Network Visibility & Asset Intelligence Framework

![main][main]

<details>
  <summary>📷 Click for more screenshots</summary>

  | ![Main screen][main] | ![device_details 1][device_details]  | ![Screen network][network] |
  |----------------------|----------------------|----------------------|
  | ![presence][presence] | ![maintenance][maintenance] | ![settings][settings]  |
  | ![sync_hub][sync_hub] | ![report1][report1] | ![device_nmap][device_nmap]  |

  Head to [https://netalertx.com/](https://netalertx.com/) for even more gifs and screenshots 📷.

</details>


Centralized network visibility and continuous asset discovery.

Monitor devices, detect change, and stay aware across distributed networks.

NetAlertX provides a centralized "Source of Truth" (NSoT) for network infrastructure. Maintain a real-time inventory of every connected device, identify Shadow IT and unauthorized hardware to maintain regulatory compliance, and automate compliance workflows across distributed sites.

NetAlertX is designed to bridge the gap between simple network scanning and complex SIEM tools, providing actionable insights without the overhead.


## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Documentation](#documentation)
- [Security \& Privacy](#security--privacy)
- [FAQ](#faq)
- [Troubleshooting Tips](#troubleshooting-tips)
- [Everything else](#everything-else)

## Quick Start

> [!WARNING]
> ⚠️ **Important:** The docker-compose has recently changed. Carefully read the [Migration guide](https://docs.netalertx.com/MIGRATION/?h=migrat#12-migration-from-netalertx-v25524) for detailed instructions.

Start NetAlertX in seconds with Docker:

```bash
docker run -d \
  --network=host \
  --restart unless-stopped \
  -v /local_data_dir:/data \
  -v /etc/localtime:/etc/localtime:ro \
  --tmpfs /tmp:uid=20211,gid=20211,mode=1700 \
  -e PORT=20211 \
  -e APP_CONF_OVERRIDE='{"GRAPHQL_PORT":"20214"}' \
  ghcr.io/netalertx/netalertx:latest
```

Note: Your `/local_data_dir` should contain a `config` and `db` folder.

To deploy a containerized instance directly from the source repository, execute the following BASH sequence:
```bash
git clone https://github.com/netalertx/NetAlertX.git
cd NetAlertX
docker compose up --force-recreate --build
# To customize: edit docker-compose.yaml and run that last command again
```

Need help configuring it? Check the [usage guide](https://docs.netalertx.com/README) or [full documentation](https://docs.netalertx.com/).

For Home Assistant users: [Click here to add NetAlertX](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Falexbelgium%2Fhassio-addons)

For other install methods, check the [installation docs](#documentation)

---
### || [Docker guide](https://docs.netalertx.com/DOCKER_INSTALLATION) || [Releases](https://github.com/netalertx/NetAlertX/releases) || [Docs](https://docs.netalertx.com/) || [Plugins](https://docs.netalertx.com/PLUGINS) || [Website](https://netalertx.com)
---

## Features

### Discovery & Asset Intelligence

Continuous monitoring for unauthorized asset discovery, connection state changes, and IP address management (IPAM) drift. Discovery & scan methods include: **arp-scan**,  **Pi-hole - DB import**,  **Pi-hole - DHCP leases import**, **Generic DHCP leases import**, **UNIFI controller import**, **SNMP-enabled router import**. Check the [Plugins](https://docs.netalertx.com/PLUGINS#readme) docs for a full list of avaliable plugins.

### Notification gateways

Send notifications to more than 80+ services, including Telegram via [Apprise](https://hub.docker.com/r/caronc/apprise), or use native [Pushsafer](https://www.pushsafer.com/), [Pushover](https://www.pushover.net/), or [NTFY](https://ntfy.sh/) publishers.

### Integrations and Plugins

Feed your data and device changes into [Home Assistant](https://docs.netalertx.com/HOME_ASSISTANT), read [API endpoints](https://docs.netalertx.com/API), or use [Webhooks](https://docs.netalertx.com/WEBHOOK_N8N) to setup custom automation flows. You can also
build your own scanners with the [Plugin system](https://docs.netalertx.com/PLUGINS#readme) in as little as [15 minutes](https://www.youtube.com/watch?v=cdbxlwiWhv8).

### Workflows

The [workflows module](https://docs.netalertx.com/WORKFLOWS) automates IT governance by enforcing device categorization and cleanup policies. Whether you need to assign newly discovered devices to a specific Network Node, auto-group devices from a given vendor, unarchive a device if detected online, or automatically delete devices, this module provides the flexibility to tailor the automations to your needs.


## Documentation
<!--- --------------------------------------------------------------------- --->

Explore all the [documentation here](https://docs.netalertx.com/) or navigate to a specific installation option below.

Supported browsers: Chrome, Firefox

- [[Installation] Docker](https://docs.netalertx.com/DOCKER_INSTALLATION)
- [[Installation] Home Assistant](https://github.com/alexbelgium/hassio-addons/tree/master/netalertx)
- [[Installation] Bare metal](https://docs.netalertx.com/HW_INSTALL)
- [[Installation] Unraid App](https://unraid.net/community/apps)
- [[Setup] Usage and Configuration](https://docs.netalertx.com/README)
- [[Development] API docs](https://docs.netalertx.com/API)
- [[Development] Custom Plugins](https://docs.netalertx.com/PLUGINS_DEV)

## Security & Privacy

NetAlertX scans your local network and can store metadata about connected devices. By default, all data is stored **locally**. No information is sent to external services unless you explicitly configure notifications or integrations.

Compliance & Hardening:
- Run it behind a reverse proxy with authentication
- Use firewalls to restrict access to the web UI
- Regularly update to the latest version for security patches
- Role-Based Access Control (RBAC) via Reverse Proxy: Integrate with your existing SSO/Identity provider for secure dashboard access.

See [Security Best Practices](https://github.com/netalertx/NetAlertX/security) for more details.


## FAQ

**Q: How do I monitor VLANs or remote subnets?**
A: Ensure the container has proper network access (e.g., use `--network host` on Linux). Also check that your scan method is properly configured in the UI.

**Q: What is the recommended deployment for high-availability?**
A: We recommend deploying via Docker with persistent volume mounts for database integrity and running behind a reverse proxy for secure access.

**Q: Will this send any data to the internet?**
A: No. All scans and data remain local, unless you set up cloud-based notifications.

**Q: Can I use this without Docker?**
A: You can install the application directly on your own hardware by following the [bare metal installation guide](https://docs.netalertx.com/HW_INSTALL).

**Q: Where is the data stored?**
A: In the `/data/config` and `/data/db` folders. Back up these folders regularly.


## Troubleshooting Tips

- Some scanners (e.g. ARP) may not detect devices on different subnets. See the [Remote networks guide](https://docs.netalertx.com/REMOTE_NETWORKS) for workarounds.
- Wi-Fi-only networks may require alternate scanners for accurate detection.
- Notification throttling may be needed for large networks to prevent spam.
- On some systems, elevated permissions (like `CAP_NET_RAW`) may be needed for low-level scanning.

Check the [GitHub Issues](https://github.com/netalertx/NetAlertX/issues) for the latest bug reports and solutions and consult [the official documentation](https://docs.netalertx.com/).

## Everything else
<!--- --------------------------------------------------------------------- --->

<a href="https://trendshift.io/repositories/12670" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12670" alt="jokob-sk%2FNetAlertX | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

### 📧 Get notified what's new

Get notified about a new release, what new functionality you can use and about breaking changes.

![Follow and star][follow_star]

### 🔀 Other Alternative Apps

- [Fing](https://www.fing.com/) - Network scanner app for your Internet security (Commercial, Phone App, Proprietary hardware)
- [NetBox](https://netboxlabs.com/) - The gold standard for Network Source of Truth (NSoT) and IPAM.
- [Zabbix](https://www.zabbix.com/) or [Nagios](https://www.nagios.org/) - Strong focus on infrastructure monitoring.
- [NetAlertX](https://netalertx.com) - The streamlined, discovery-focused choice for real-time asset intelligence and noise-free alerting.

### 💙 Donations

Thank you to everyone who appreciates this tool and donates.

<details>
  <summary>Click for more ways to donate</summary>

  <hr>

  | [![GitHub](https://i.imgur.com/emsRCPh.png)](https://github.com/sponsors/jokob-sk) | [![Buy Me A Coffee](https://i.imgur.com/pIM6YXL.png)](https://www.buymeacoffee.com/jokobsk) |
  | --- | --- |
  - Bitcoin: `1N8tupjeCK12qRVU2XrV17WvKK7LCawyZM`
  - Ethereum: `0x6e2749Cb42F4411bc98501406BdcD82244e3f9C7`

  📧 Email me at [jokob@duck.com](mailto:jokob@duck.com?subject=NetAlertX) if you want to get in touch or if I should add other sponsorship platforms.

</details>

### 🏗 Contributors

This project would be nothing without the amazing work of the community, with special thanks to:

> [pucherot/Pi.Alert](https://github.com/pucherot/Pi.Alert) (the original creator of PiAlert), [leiweibau](https://github.com/leiweibau/Pi.Alert): Dark mode (and much more), [Macleykun](https://github.com/Macleykun) (Help with Dockerfile clean-up), [vladaurosh](https://github.com/vladaurosh) for Alpine re-base help, [Final-Hawk](https://github.com/Final-Hawk) (Help with NTFY, styling and other fixes), [TeroRERO](https://github.com/terorero) (Spanish translations), [Data-Monkey](https://github.com/Data-Monkey), (Split-up of the python.py file and more), [cvc90](https://github.com/cvc90) (Spanish translation and various UI work) to name a few. Check out all the [amazing contributors](https://github.com/netalertx/NetAlertX/graphs/contributors).

### 🌍 Translations

Proudly using [Weblate](https://hosted.weblate.org/projects/pialert/). Help out and suggest languages in the [online portal of Weblate](https://hosted.weblate.org/projects/pialert/core/).

<a href="https://hosted.weblate.org/engage/pialert/">
  <img src="https://hosted.weblate.org/widget/pialert/core/multi-auto.svg" alt="Translation status" />
</a>

### License
>  GPL 3.0 | [Read more here](LICENSE.txt) | Source of the [animated GIF (Loading Animation)](https://commons.wikimedia.org/wiki/File:Loading_Animation.gif) | Source of the [selfhosted Fonts](https://github.com/adobe-fonts/source-sans)

_All product names, logos, and brands are property of their respective owners. All company, product and service names used in this website are for identification purposes only. Use of these names, logos, and brands does not imply endorsement._

<!--- --------------------------------------------------------------------- --->
[main]:                     ./docs/img/devices_split.png                  "Main screen"
[device_details]:           ./docs/img/device_details.png                 "Screen 1"
[events]:                   ./docs/img/events.png                         "Screen 2"
[presence]:                 ./docs/img/presence.png                       "Screen 3"
[maintenance]:              ./docs/img/maintenance.png                    "Screen 4"
[network]:                  ./docs/img/network.png                        "Screen 5"
[settings]:                 ./docs/img/settings.png                       "Screen 6"
[showcase]:                 ./docs/img/showcase.gif                       "Screen 6"
[sync_hub]:                 ./docs/img/sync_hub.png                       "Screen 8"
[notification_center]:      ./docs/img/notification_center.png            "Screen 8"
[sent_reports_text]:        ./docs/img/sent_reports_text.png              "Screen 8"
[device_nmap]:              ./docs/img/device_tools.png                    "Screen 9"
[report1]:                  ./docs/img/report_sample.png                  "Report sample 1"
[main_dark]:                /docs/img/1_devices_dark.jpg                  "Main screen dark"
[maintain_dark]:            /docs/img/5_maintain.jpg                      "Maintain screen dark"
[follow_star]:              /docs/img/Follow_Releases_and_Star.gif        "Follow and Star"
