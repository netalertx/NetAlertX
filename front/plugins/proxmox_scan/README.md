# Proxmox Device Scan Plugin for NetAlertX

This plugin scans Proxmox nodes, VMs, and containers, mapping parent-child relationships and extracting MAC addresses for device mapping in NetAlertX.

## Setup
1. Place this folder (`proxmox_scan`) in `NetAlertX/front/plugins/`.
2. Configure the plugin in the NetAlertX UI with your Proxmox API URL, user, and API token.

## Requirements
- Python 3.x
- `requests` library

## Configuration
- `api_url`: Proxmox API endpoint (e.g., `https://proxmox.example.com:8006`)
- `api_user`: Proxmox user (e.g., `root@pam`)
- `api_token`: Proxmox API token (format: `USER@REALM!TOKENID=SECRET`)

## Output Columns
- id | parent_id | type | name | mac | ip | desc | os | extra

## Example Usage
This plugin is invoked by NetAlertX. No manual execution is required.

## Debugging
- Debug output is written to `debug.log` in the plugin directory.
