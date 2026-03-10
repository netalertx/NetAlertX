# Development Environment Setup

I truly appreciate all contributions! To help keep this project maintainable, this guide provides an overview of project priorities, key design considerations, and overall philosophy. It also includes instructions for setting up your environment so you can start contributing right away.

## Development Guidelines

Before starting development, please review the following guidelines.

### Priority Order (Highest to Lowest)

1. 🔼 Fixing core bugs that lack workarounds
2. 🔵 Adding core functionality that unlocks other features (e.g., plugins)
3. 🔵 Refactoring to enable faster development
4. 🔽 UI improvements (PRs welcome, but low priority)

### Design Philosophy

The application architecture is designed for extensibility and maintainability. It relies heavily on configuration manifests via plugins and settings to dynamically build the UI and populate the application with data from various sources.

For details, see:
- [Plugins Development](PLUGINS_DEV.md) (includes video)
- [Settings System](SETTINGS_SYSTEM.md)

Focus on **core functionality** and integrate with existing tools rather than reinventing the wheel.

Examples:
- Using **Apprise** for notifications instead of implementing multiple separate gateways
- Implementing **regex-based validation** instead of one-off validation for each setting

> [!NOTE]
> UI changes have lower priority. PRs are welcome, but please keep them **small and focused**.

## Development Environment Set Up

>[!TIP]
> There is also a ready to use [devcontainer](DEV_DEVCONTAINER.md) available.

The following steps will guide you to set up your environment for local development and to run a custom docker build on your system. For most changes the container doesn't need to be rebuild which speeds up the development significantly.

>[!NOTE]
> Replace `/development` with the path where your code files will be stored. The default container name is `netalertx` so there might be a conflict with your running containers.

### 1. Download the code:

- `mkdir /development`
- `cd /development && git clone https://github.com/netalertx/NetAlertX.git`

### 2. Create a DEV .env_dev file

`touch /development/.env_dev && sudo nano /development/.env_dev`

The file content should be following, with your custom values.

```yaml
#--------------------------------
#NETALERTX
#--------------------------------
PORT=22222    # make sure this port is unique on your whole network
DEV_LOCATION=/development/NetAlertX
APP_DATA_LOCATION=/volume/docker_appdata
# Make sure your GRAPHQL_PORT setting has a port that is unique on your whole host network
APP_CONF_OVERRIDE={"GRAPHQL_PORT":"22223"}
# ALWAYS_FRESH_INSTALL=true # uncommenting this will always delete the content of /config and /db dirs on boot to simulate a fresh install
```

### 3. Create /db and /config dirs

Create a folder `netalertx` in the `APP_DATA_LOCATION` (in this example in `/volume/docker_appdata`) with 2 subfolders `db` and `config`.

- `mkdir /volume/docker_appdata/netalertx`
- `mkdir /volume/docker_appdata/netalertx/db`
- `mkdir /volume/docker_appdata/netalertx/config`

### 4. Run the container

- `cd /development/NetAlertX &&  sudo docker-compose --env-file ../.env_dev `

You can then modify the python script without restarting/rebuilding the container every time. Additionally, you can trigger a plugin run via the UI:

![image](https://github.com/netalertx/NetAlertX/assets/96159884/3cbf2748-03c8-49e7-b801-f38c7755246b)


## Tips

A quick cheat sheet of useful commands.

### Removing the container and image

A command to stop, remove the container and the image (replace `netalertx` and `netalertx-netalertx` with the appropriate values)

- `sudo docker container stop netalertx ; sudo docker container rm netalertx ; sudo docker image rm netalertx-netalertx`

### Restart the server backend

Most code changes can be tested without rebuilding the container. When working on the python server backend, you only need to restart the server.

1. You can usually restart the backend via _Maintenance > Logs > Restart_ server

![image](./img/DEV/Maintenance_Logs_Restart_server.png)

2. If above doesn't work, SSH into the container and kill & restart the main script loop

- `sudo docker exec -it netalertx /bin/bash`
- `pkill -f "python /app/server" && python /app/server & `

3. If none of the above work, restart the docker container.

- This is usually the last resort as sometimes the Docker engine becomes unresponsive and the whole engine needs to be restarted.

## Contributing & Pull Requests

### Before submitting a PR, please ensure:

✔ Changes are **backward-compatible** with existing installs.
✔ No unnecessary changes are made.
✔ New features are **reusable**, not narrowly scoped.
✔ Features are implemented via **plugins** if possible.

### Mandatory Test Cases

- Fresh install (no DB/config).
- Existing DB/config compatibility.
- Notification testing:

    - Email
    - Apprise (e.g., Telegram)
    - Webhook (e.g., Discord)
    - MQTT (e.g., Home Assistant)

- Updating Settings and their persistence.
- Updating a Device
- Plugin functionality.
- Error log inspection.

> [!NOTE]
> Always run all available tests as per the [Testing documentation](API_TESTS.md).
