# NetAlertX OPNsense DHCP Lease Converter

## Overview

This script retrieves DHCP lease data from an OPNsense firewall over SSH and converts it into the `dnsmasq` lease file format. You can combine it with the `DHCPLLSS` plugin to ingest devices from OPNsense.

## Features
- Connects to OPNsense via SSH to retrieve DHCP lease data.
- Parses active DHCP leases.
- Converts lease data to `dnsmasq` lease format.
- Saves the converted lease file to a specified output location.
- Supports password and key-based SSH authentication.
- Includes a debug mode for troubleshooting.

## Requirements
- Python 3
- `paramiko` library (for SSH connection)
- An OPNsense firewall with SSH access enabled

## Usage
Run the script with the required parameters:

```sh
./script.py --host <OPNsense_IP> --username <SSH_User> --output <Output_File>
```

### Available Options

| Option        | Description |
|--------------|-------------|
| `--host`     | OPNsense hostname or IP address (Required) |
| `--username` | SSH username (Required) |
| `--password` | SSH password (Optional if using key-based authentication) |
| `--key-file` | Path to SSH private key file (Optional) |
| `--port`     | SSH port (Default: 22) |
| `--output`   | Output file path for converted lease file (Required) |
| `--debug`    | Enable debug logging (Optional) |

### Example Commands

#### Install Requirements

You will need to install dependencies in the container:

```bash
pip install paramiko
```

You could achieve this by mounting a custom cron file to `/etc/crontabs/root`:

```bash
# Schedule cron jobs
* * * * * /app/back/cron_script.sh
* * * * * /opt/venv/bin/python3 -c "import paramiko" || (/opt/venv/bin/pip install paramiko >/dev/null 2>&1 && sed -i '/pip install paramiko/d' /etc/crontabs/root)
```

Please double check the [default cron file](https://github.com/netalertx/NetAlertX/blob/main/install/crontab) hasn't changed.

#### Using Password Authentication
```sh
./script.py --host 192.168.1.1 --username admin --password mypassword --output /tmp/dnsmasq.leases
```

#### Using SSH Key Authentication
```sh
./script.py --host 192.168.1.1 --username admin --key-file ~/.ssh/id_rsa --output /tmp/dnsmasq.leases
```

## Output Format
The script generates a `dnsmasq`-formatted lease file with lines structured as:

```
[epoch timestamp] [MAC address] [IP address] [hostname] [client ID]
```

Example:
```sh
1708212000 00:11:22:33:44:55 192.168.1.100 my-device 01:00:11:22:33:44:55
```

## Troubleshooting

- **Connection issues?** Ensure SSH is enabled on the OPNsense device and the correct credentials are used.
- **No lease data?** Verify the DHCP lease file exists at `/var/dhcpd/var/db/dhcpd.leases`.
- **Permission denied?** Ensure your SSH user has the required permissions to access the lease file.
- **Debugging:** Run the script with the `--debug` flag to see more details.


### Other info

- Version: 1.0
- Author: [im-redactd](https://github.com/im-redactd)
- Release Date: 24-Feb-2025

> [!NOTE]
> This is a community supplied script and not maintained.