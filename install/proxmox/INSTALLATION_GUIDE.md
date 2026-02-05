# NetAlertX Installation Guide for Proxmox VE

## Quick Start (ProxmoxVE LXC Container)

To create a NetAlertX LXC container on Proxmox VE, run this command on your Proxmox host:

```bash
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/netalertx.sh)"
```

This will:
- Create a Debian 13 LXC container
- Install all dependencies automatically
- Configure NetAlertX with NGINX on port 20211
- Start the service automatically

### Update Existing Installation

To update an existing NetAlertX container:

```bash
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/netalertx.sh)" -s update
```

---

## Installation Process Overview

### 1. **System Preparation**
- Updates system packages

### 2. **Dependency Installation**
- Installs NGINX web server
- Installs Python 3 and development tools
- Installs network scanning tools (nmap, arp-scan, fping, etc.)
- Installs system utilities (sqlite3, dnsutils, avahi-daemon, etc.)

### 3. **Application Setup**
- Clones NetAlertX repository to `/app`
- Creates Python virtual environment at `/opt/netalertx-env`
- Installs Python dependencies from requirements.txt
- Configures NGINX with default port 20211

### 4. **File Structure Creation**
- Creates persistent directories for `/app/log` and `/app/api`
- Creates log files and plugin directories
- Copies initial database and configuration files
- Sets secure file permissions (www-data user/group)
- Configures systemd RuntimeDirectory (`/run/netalertx`) for volatile service files

### 5. **Service Configuration**
- Creates startup script at `/app/start.netalertx.sh`
- Installs systemd service (`netalertx.service`)
- Enables auto-start on boot
- Starts NetAlertX and NGINX services

### 6. **Hardware Vendor Database**
- Updates IEEE OUI database for MAC address vendor identification (if not present)

---

## Post-Installation

### Accessing NetAlertX

After successful installation, access the web interface at:

```
http://YOUR_SERVER_IP:YOUR_PORT
```

**Default port**: 20211

To find your server IP:
```bash
ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}'
```

### Service Management

```bash
# Check service status
systemctl status netalertx.service

# View real-time logs
journalctl -u netalertx.service -f

# Restart service
systemctl restart netalertx.service

# Stop service
systemctl stop netalertx.service
```

---

## Important File Locations

| Component | Location |
|-----------|----------|
| Installation Directory | `/app` |
| Configuration File | `/app/config/app.conf` |
| Database File | `/app/db/app.db` |
| NGINX Configuration | `/etc/nginx/conf.d/netalertx.conf` |
| Web UI (symlink) | `/var/www/html/netalertx` → `/app/front` |
| Python Virtual Env | `/opt/netalertx-env` |
| Systemd Service | `/etc/systemd/system/netalertx.service` |
| Startup Script | `/app/start.netalertx.sh` |
| Application Logs | `/app/log/` (persistent) |
| API Files | `/app/api/` (persistent) |
| Service Runtime | `/run/netalertx/` (tmpfs, systemd-managed) |

### Storage Strategy (Hybrid Approach)

**Persistent Storage** (survives reboots):
- `/app/log/app.log` - Main application log
- `/app/log/execution_queue.log` - Task execution log
- `/app/log/app_front.log` - Frontend log
- `/app/log/app.php_errors.log` - PHP error log
- `/app/log/stderr.log` - Standard error output
- `/app/log/stdout.log` - Standard output
- `/app/log/db_is_locked.log` - Database lock log
- `/app/api/user_notifications.json` - User notification data

**Volatile Storage** (tmpfs, cleared on reboot):
- `/run/netalertx/` - Systemd-managed runtime directory for service temporary files

Systemd service logs are always available via: `journalctl -u netalertx.service`

---

## Environment Variables

The installation script supports the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `NETALERTX_ASSUME_YES` | Skip all interactive prompts | (not set) |
| `ASSUME_YES` | Alternative to NETALERTX_ASSUME_YES | (not set) |
| `PORT` | HTTP port for web interface | 20211 |
| `NETALERTX_FORCE` | Force installation without prompts | (not set) |

---

## Security Considerations

- **Runtime directory**: Systemd manages `/run/netalertx/` as tmpfs with `noexec,nosuid,nodev` flags
- **File permissions**: Application files restricted to `www-data` user/group only (mode 0750)
- **Service isolation**: Runs as unprivileged `www-data` user
- **Automatic restart**: Service configured to restart on failure
- **Persistent logs**: Application logs survive reboots for debugging and audit trails

---

## Additional Resources

- **GitHub Repository**: https://github.com/jokob-sk/NetAlertX
- **Issue Tracker**: https://github.com/jokob-sk/NetAlertX/issues
- **Documentation**: `/app/docs/` directory
