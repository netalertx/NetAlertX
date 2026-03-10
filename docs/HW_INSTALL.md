# How to install NetAlertX on the server hardware

To download and install NetAlertX on the hardware/server directly use the `curl` or `wget` commands at the bottom of this page.

> [!NOTE]
> This is an Experimental feature 🧪 and it relies on community support.
>
> 🙏 Looking for maintainers for this installation method 🙂 Current community volunteers:
>   - [slammingprogramming](https://github.com/slammingprogramming)
>   - [ingoratsdorf](https://github.com/ingoratsdorf)
>
> There is no guarantee that the install script or any other script will gracefully handle other installed software.
> Data loss is a possibility, **it is recommended to install NetAlertX using the supplied Docker image**.

> [!WARNING]
> A warning to the installation method below: Piping to bash is [controversial](https://pi-hole.net/2016/07/25/curling-and-piping-to-bash) and may be dangerous, as you cannot see the code that's about to be executed on your system.

If you trust this repo, you can download the install script via one of the methods (curl/wget) below and it will fo its best to install NetAlertX on your system.

Alternatively you can download the installation script from the repository and check the code yourself.

NetAlertX will be installed in `/app` and run on port number `20211`.

Some facts about what and where something will be changed/installed by the HW install setup (may not contain everything!):

- dependencies will be installed from the respective system repos
- required python modules will be installed
- `/app` directory will be deleted and newly created
- `/app` will contain the whole repository (downloaded by the install script)
- The default NGINX site `/etc/nginx/sites-enabled/default` will be disabled (sym-link deleted or backed up to `sites-available`)
- `/var/www/html/netalertx` directory will be deleted and newly created
- `/etc/nginx/conf.d/netalertx.conf` will be sym-linked to the appropriate installer location (depending on your system installer script)
- Some files (IEEE device vendors info, ...) will be created in the directory where the installation script is executed

## Limitations

- No system service is provided. NetAlertX must be started using `/app/install/<system>/start.<system>.sh`.
- No checks for other running software is done.
- Only tested to work on the system listed in the install directory.
- **EXPERIMENTAL** and not recommended way to install NetAlertX.

> [!TIP]
> If the below fails try grabbing and installing one of the [previous releases](https://github.com/netalertx/NetAlertX/releases) and run the installation from the zip package.

These commands will download the `install.debian12.sh` script from the GitHub repository, make it executable with `chmod`, and then run it using `./install.debian12.sh`.

Make sure you have the necessary permissions to execute the script.


## 📥 Debian 12 (Bookworm)

### Installation via curl
```bash
curl -o install.debian12.sh https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/install/debian12/install.debian12.sh && sudo chmod +x install.debian12.sh && sudo ./install.debian12.sh
```

### Installation via wget

```bash
wget https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/install/debian12/install.debian12.sh -O install.debian12.sh && sudo chmod +x install.debian12.sh && sudo ./install.debian12.sh
```

## 📥 Ubuntu 24 (Noble Numbat)

> [!NOTE]
> Maintained by [ingoratsdorf](https://github.com/ingoratsdorf)

### Installation via curl
```bash
curl -o install.sh https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/install/ubuntu24/install.sh && sudo chmod +x install.sh && sudo ./install.sh
```

### Installation via wget

```bash
wget https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/install/ubuntu24/install.sh -O install.sh && sudo chmod +x install.sh && sudo ./install.sh
```

## 📥 Bare Metal - Proxmox

> [!NOTE]
> Use this on a clean LXC/VM for Debian 13 OR Ubuntu 24.
> The Scipt will detect OS and build acordingly.
> Maintained by [JVKeller](https://github.com/JVKeller)

### Installation via wget
```bash
wget https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/install/proxmox/proxmox-install-netalertx.sh -O proxmox-install-netalertx.sh && chmod +x proxmox-install-netalertx.sh && ./proxmox-install-netalertx.sh
```
