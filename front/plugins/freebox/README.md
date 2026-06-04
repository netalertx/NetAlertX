## Overview

Plugin to pull devices, IPs, and their names from a Freebox or Iliadbox gateway.

### Pairing

Requirements:
- Physical access to the Freebox
- Network access to the same lan as the Freebox

Regardless of which setup you will choose, you will first need to pair NetAlertX to your Freebox. To pair, the device running NetAlertX *must* be connected on the same lan as the Freebox. After pairing, the device can access your Freebox even from the Internet (se [remote setup](#remote-setup)).

To pair, you can leave the settings to their default values (same as [quick setup](#quick-setup)), though other configurations will work as well if you can't use the default one.

When you run the plugin the first time, it will send a pairing request to the Freebox, if you look at the logs you will see a message saying to *"Continue the pairing on your Freebox"*. At this point, on the front panel of the Freebox you will see an authorization request, confirm it using the buttons on the front panel to complete the pairing.
If you don't see the message on the logs, something is preventing the plugin from running.

Note: You can screen and revoke any previous authorization (completed or attempted) from the web interface of your Freebox.

### Quick setup

Note: read [pairing](#pairing) first.

By default the plugin will connect to the address `mafreebox.freebox.fr` on the HTTPS port `443`, if you have an Iliadbox, replace the address with `myiliadbox.iliad.it`. This will work in most cases, but has some limitations.

Limitations:
- It requires internet access
- The Freebox must be your gateway
- The device must be in the same lan as the Freebox

### Remote setup

Use this configuration if you wish to connect to your Freebox through the internet. You still need to pair from the local network.

If the Freebox is your gateway you need to find its HTTPS (or HTTP if you prefer) public port. This can be found either in the Freeboxe's web interface and by navigating to `settings>access management`, or (just for the HTTPS port) by visiting http://mafreebox.freebox.fr:80/api_version from the local network (you can use the local ip as well). This is the port you need to access your Freebox through the internet

As address, you can either use the public IP of the Freebox, or the unique domain name you found on http://mafreebox.freebox.fr:80/api_version listed as `api_domain`.

## Other info

- Version: 2.0
- Author: [KayJay7](https://github.com/KayJay7), [Lucide](https://github.com/Lucide)
- Maintainers: [mathoudebine](https://github.com/mathoudebine)
- Release Date: 2-Dec-2024