# Debugging and troubleshooting

Please follow tips 1 - 4 to get a more detailed error.

## 1. More Logging

When debugging an issue always set the highest log level in **Settings -> Core**:

`LOG_LEVEL='trace'`

## 2. Surfacing errors when container restarts

Start the container via the **terminal** with a command similar to this one:

```bash
docker run \
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

> [!NOTE]
> ⚠ The most important part is NOT to use the `-d` parameter so you see the error when the container crashes. Use this error in your issue description.

## 3. Check the _dev image and open issues

If possible, check if your issue got fixed in the `_dev` image before opening a new issue. The container is:

`ghcr.io/netalertx/netalertx-dev:latest`

> ⚠ Please backup your DB and config beforehand!

Please also search [open issues](https://github.com/netalertx/NetAlertX/issues).

## 4. Disable restart behavior

To prevent a Docker container from automatically restarting in a Docker Compose file, specify the restart policy as `no`:

```yaml
version: '3'

services:
  your-service:
    image: your-image:tag
    restart: no
    # Other service configurations...
```

## 5. TMP mount directories to rule host out permission issues

Try starting the container with all data to be in non-persistent volumes. If this works, the issue might be related to the permissions of your persistent data mount locations on your server. See teh [Permissions guide](./FILE_PERMISSIONS.md) for details.


## 6. Sharing application state

Sometimes specific log sections are needed to debug issues. The Devices and CurrentScan table data is sometimes needed to figure out what's wrong.

1. Please set `LOG_LEVEL` to `trace` (Disable it once you have the info as this produces big log files).
2. Wait for the issue to occur.
3. Search for `================ DEVICES table content  ================` in your logs.
4. Search for `================ CurrentScan table content  ================` in your logs.
5. Open a new issue and post (redacted) output into the issue description (or send to the netalertx@gmail.com email if sensitive data present).
6. Please set `LOG_LEVEL` to `debug` or lower.

## Common issues

See [Common issues](./COMMON_ISSUES.md) for additional troubleshooting tips.
