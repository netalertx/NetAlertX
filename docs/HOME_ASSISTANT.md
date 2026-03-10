# Home Assistant integration overview

NetAlertX comes with MQTT support, allowing you to show all detected devices as devices in Home Assistant. It also supplies a collection of stats, such as number of online devices.

> [!TIP]
> You can install NetAlertX also as a Home Assistant addon [![Home Assistant](https://img.shields.io/badge/Repo-blue?logo=home-assistant&style=for-the-badge&color=0aa8d2&logoColor=fff&label=Add)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Falexbelgium%2Fhassio-addons) via the [alexbelgium/hassio-addons](https://github.com/alexbelgium/hassio-addons/) repository. This is only possible if you run a supervised instance of Home Assistant. If not, you can still run NetAlertX in a separate Docker container and follow this guide to configure MQTT.

## ⚠ Note

- Please note that discovery takes about ~10s per device.
- Deleting of devices is not handled automatically. Please use [MQTT Explorer](https://mqtt-explorer.com/) to delete devices in the broker (Home Assistant), if needed.
- For optimization reasons, the devices are not always fully synchronized. You can delete Plugin objects as described in the [MQTT plugin](https://github.com/netalertx/NetAlertX/tree/main/front/plugins/_publisher_mqtt#forcing-an-update) docs to force a full synchronization.


## 🧭 Guide

> 💡 This guide was tested only with the Mosquitto MQTT broker

1. Enable Mosquitto MQTT in Home Assistant by following the [documentation](https://www.home-assistant.io/integrations/mqtt/)

2. Configure a user name and password on your broker.

3. Note down the following details that you will need to configure NetAlertX:

      - MQTT host url (usually your Home Assistant IP)
      - MQTT broker port
      - User
      - Password

4. Open the _NetAlertX_ > _Settings_ > _MQTT_ settings group

      - Enable MQTT
      - Fill in the details from above
      - Fill in remaining settings as per description
      - set MQTT_RUN to schedule or on_notification depending on requirements

![Configuration Example][configuration]

## 📷 Screenshots

  | ![Screen 1][sensors] | ![Screen 2][history] |
  |----------------------|----------------------|
  | ![Screen 3][list] | ![Screen 4][overview] |


  [configuration]:   ./img/HOME_ASISSTANT/HomeAssistant-Configuration.png           "configuration"
  [sensors]:         ./img/HOME_ASISSTANT/HomeAssistant-Device-as-Sensors.png       "sensors"
  [history]:         ./img/HOME_ASISSTANT/HomeAssistant-Device-Presence-History.png "history"
  [list]:            ./img/HOME_ASISSTANT/HomeAssistant-Devices-List.png            "list"
  [overview]:        ./img/HOME_ASISSTANT/HomeAssistant-Overview-Card.png           "overview"

## Troubleshooting

If you can't see all devices detected, run `sudo arp-scan  --interface=eth0 192.168.1.0/24` (change these based on your setup, read [Subnets](./SUBNETS.md) docs for details). This command has to be executed the NetAlertX container, not in the Home Assistant container.

You can access the NetAlertX container via Portainer on your host or via ssh. The container name will be something like `addon_db21ed7f_netalertx` (you can copy the `db21ed7f_netalertx` part from the browser when accessing the UI of NetAlertX).

## Accessing the NetAlertX container via SSH

1. Log into your Home Assistant host via SSH

```bash
local@local:~ $ ssh pi@192.168.1.9
```
2. Find the NetAlertX container name, in this case `addon_db21ed7f_netalertx`

```bash
pi@raspberrypi:~ $ sudo docker container ls | grep netalertx
06c540d97f67   ghcr.io/alexbelgium/netalertx-armv7:25.3.1                   "/init"               6 days ago      Up 6 days (healthy)    addon_db21ed7f_netalertx
```

3. SSH into the NetAlertX cointainer

```bash
pi@raspberrypi:~ $ sudo docker exec -it addon_db21ed7f_netalertx  /bin/sh
/ #
```

4. Execute a test `asrp-scan` scan

```bash
/ # sudo arp-scan --ignoredups --retry=6 192.168.1.0/24 --interface=eth0
Interface: eth0, type: EN10MB, MAC: dc:a6:32:73:8a:b1, IPv4: 192.168.1.9
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.1.1     74:ac:b9:54:09:fb       Ubiquiti Networks Inc.
192.168.1.21    74:ac:b9:ad:c3:30       Ubiquiti Networks Inc.
192.168.1.58    1c:69:7a:a2:34:7b       EliteGroup Computer Systems Co., LTD
192.168.1.57    f4:92:bf:a3:f3:56       Ubiquiti Networks Inc.
...
```

If your result doesn't contain results similar to the above, double check your subnet, interface and if you are dealing with an inaccessible network segment, read the [Remote networks documentation](./REMOTE_NETWORKS.md).