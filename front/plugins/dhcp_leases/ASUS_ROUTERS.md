# Configuring the `DHCPLSS` plugin to import clients from the YazFi plugin

## Requirements:

1. Only for ASUS routers with the Merlin FW and Entware installed
2. You have guest networks modified with the YazFi pluginwith unidirectional communication from the private network to the guest network configured:
  -  One way to guest: Yes

## Problem: Clients inaccessible with the Asus API:

- When using YazFi on an ASUS router, the guest clients will no longer be displayed in the regular client list
- The guests are logged in the YazFi plugin and the networks are in an advanced mode
- The `ASUSWRT` plugin by [labmonkey](https://github.com/labmonkey) can only access the clients from the Asus client list but not the guests in the YazFi plugin

## Solution: Getting the `dnsmasq.leases` from the Asus router and configuriong the `DHCPLSS` plugin:


1. Enable SSH login on your Asus router
2. Generate a pair of SSH keys and place them inside `/root/.ssh/`
3. In your router's admin-settings, paste the public key and disable "password login" for SSH
4. On your docker machine, create a script (I placed it in /home/root):
- Replace the IP if necessary.
- Replace `ssh2_privateKey` and `asususer` with your keyfile and your routers login name.
- Replace `/mnt/service-data/netalertx_dhcp.leases/` with your preferred save path inside the docker machine.

`nano grabdnsmasq.sh`

```bash
#!/bin/bash
rsync -avzh -e "ssh -i /root/.ssh/ssh2_privateKey" asususer@192.168.1.1:/var/lib/misc/dnsmasq.leases /mnt/service-data/netalertx_dhcp.leases/
```

5. Create a config file in `/root/.ssh/`:

- Again, replace the IP, the SSH key and the user and also the port if necessary

```
Host ASUS-GT-AXE16000
    HostName 192.168.1.1
    IdentityFile /root/.ssh/ssh2_privateKey
    IdentitiesOnly yes
    User asususer
    Port 22
```
6. Try a dry run with the command in step 4. If everything is fine, you should have a `dnsmasq.leases` file at your target location

> [!NOTE]
> You can also use ed25519 keys with passphrases. That makes the rsync command a little bit more complex.
> First, one have to install sshpass: apt-get install sshpass
> 1. create a file with your password that is required for the SSH key: `nano .password`
> 2. Then change the `grabdnsmasq.sh` to: `#!/bin/bash sshpass -P passphrase -f '/root/.password' rsync -avzh -e 'ssh -i /root/.ssh/<yourprivatekey>' <asususer>@192.168.1.1:/var/lib/misc/dnsmasq.leases /mnt/service-data/netalertx_dhcp.leases/`
> 3. replace:
>  -  `/root/.password` to the path of the `.password` file
>  -  `/root/.ssh/yourprivatekey` to the path of your private SSH key that is required for the ASUS router
>  -  `asususer` to the login name of your ASUS router (standard is `admin`, not recommended)
>  -  IP address of the ASUS router
>  -  Path where rsync should copy the dhcp file (it should be a mounted path to NetAlertX) - here I use `/mnt/service-data/netalertx_dhcp.leases/`

7. Edit crontab for root:

`crontab -e`

add your scheduled time and the path to your script file:

`*/2 * * * * /root/grabdnsmasq.sh`

8. Save and reload the cron service:

`service cron reload`

9. Load the `DHCPLSS` plugin in NetAlertX and add the newly generated dhcp.leases file into the container with a path that must contain the string `dnsmasq`. An example of the mount point could be:

```yaml
volumes:
      - /mnt/service-data/netalertx_dhcp.leases:/etc/dnsmasq
      ...
```

10. Load the `DHCPLSS` plugin and add the search path: `/etc/dnsmasq/dnsmasq.leases`

Configure the plugin, and save everything. You can trigger a manual run.

> [!NOTE]
> DHCP leases don't allow for realtime tracking and the freshness of the data depends on the DHCP leasing time (usually set to 1 or 24h, or 3600 to 86400 seconds).

For a Docker LXC setup the file could be located at `/mnt/service-data/netalertx_dhcp.leases/dnsmasq.leases`.

## Quick setup overview:

```python
DHCPLSS_RUN: 'schedule'
DHCPLSS_CMD: 'python3 /app/front/plugins/dhcp_leases/script.py paths={paths}'
DHCPLSS_paths_to_check: ['/etc/dnsmasq/dnsmasq.leases']
DHCPLSS_RUN_SCHD: '*/5 * * * *'
DHCPLSS_TUN_TIMEOUT: 5
DHCPLSS_WATCH: ['watchedValue1', 'watchedValue4']
DHCPLSS_REPORT_ON: ['new', 'watched-changed']
```

You can check the the `dnsmasq.leases` file in the container by running `ls /etc/dnsmasq/`:

```bash
CT_NetAlertX:/# ls /etc/dnsmasq/
dnsmasq.leases
```

## Other Info

- Publishing date: 22.1.2025
- Author: [EinKantHolz - odin](https://github.com/EinKantHolz)