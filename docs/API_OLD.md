# [Deprecated] API endpoints

> [!WARNING]
> Some of these endpoints will be deprecated soon. Please refere to the new [API](API.md) endpoints docs for details on the new API layer.

NetAlertX comes with a couple of API endpoints. All requests need to be authorized (executed in a logged in browser session) or you have to pass the value of the `API_TOKEN` settings as authorization bearer, for example:

```graphql
curl 'http://host:GRAPHQL_PORT/graphql' \
  -X POST \
  -H 'Authorization: Bearer API_TOKEN' \
  -H 'Content-Type: application/json' \
  --data '{
    "query": "query GetDevices($options: PageQueryOptionsInput) { devices(options: $options) { devices { rowid devMac devName devOwner devType devVendor devLastConnection devStatus } count } }",
    "variables": {
      "options": {
        "page": 1,
        "limit": 10,
        "sort": [{ "field": "devName", "order": "asc" }],
        "search": "",
        "status": "connected"
      }
    }
  }'
```

## API Endpoint: GraphQL

- Endpoint URL: `php/server/query_graphql.php`
- Host: `same as front end (web ui)`
- Port: `20212` or as defined by the `GRAPHQL_PORT` setting

### Example Query to Fetch Devices

First, let's define the GraphQL query to fetch devices with pagination and sorting options.

```graphql
query GetDevices($options: PageQueryOptionsInput) {
  devices(options: $options) {
    devices {
      rowid
      devMac
      devName
      devOwner
      devType
      devVendor
      devLastConnection
      devStatus
    }
    count
  }
}
```

See also: [Debugging GraphQL issues](./DEBUG_API_SERVER.md)

### `curl` Command

You can use the following `curl` command to execute the query.

```sh
curl 'http://host:GRAPHQL_PORT/graphql'   -X POST   -H 'Authorization: Bearer API_TOKEN'  -H 'Content-Type: application/json'   --data '{
    "query": "query GetDevices($options: PageQueryOptionsInput) { devices(options: $options) { devices { rowid devMac devName devOwner devType devVendor devLastConnection devStatus } count } }",
    "variables": {
      "options": {
        "page": 1,
        "limit": 10,
        "sort": [{ "field": "devName", "order": "asc" }],
        "search": "",
        "status": "connected"
      }
    }
  }'
```

### Explanation:

1. **GraphQL Query**:
   - The `query` parameter contains the GraphQL query as a string.
   - The `variables` parameter contains the input variables for the query.

2. **Query Variables**:
   - `page`: Specifies the page number of results to fetch.
   - `limit`: Specifies the number of results per page.
   - `sort`: Specifies the sorting options, with `field` being the field to sort by and `order` being the sort order (`asc` for ascending or `desc` for descending).
   - `search`: A search term to filter the devices.
   - `status`: The status filter to apply (valid values are `my_devices` (determined by the `UI_MY_DEVICES` setting), `connected`, `favorites`, `new`, `down`, `archived`, `offline`).

3. **`curl` Command**:
   - The `-X POST` option specifies that we are making a POST request.
   - The `-H "Content-Type: application/json"` option sets the content type of the request to JSON.
   - The `-d` option provides the request payload, which includes the GraphQL query and variables.

### Sample Response

The response will be in JSON format, similar to the following:

```json
{
  "data": {
    "devices": {
      "devices": [
        {
          "rowid": 1,
          "devMac": "00:11:22:33:44:55",
          "devName": "Device 1",
          "devOwner": "Owner 1",
          "devType": "Type 1",
          "devVendor": "Vendor 1",
          "devLastConnection": "2025-01-01T00:00:00Z",
          "devStatus": "connected"
        },
        {
          "rowid": 2,
          "devMac": "66:77:88:99:AA:BB",
          "devName": "Device 2",
          "devOwner": "Owner 2",
          "devType": "Type 2",
          "devVendor": "Vendor 2",
          "devLastConnection": "2025-01-02T00:00:00Z",
          "devStatus": "connected"
        }
      ],
      "count": 2
    }
  }
}
```

## API Endpoint: JSON files

This API endpoint retrieves static files, that are periodically updated.

- Endpoint URL: `php/server/query_json.php?file=<file name>`
- Host: `same as front end (web ui)`
- Port: `20211` or as defined by the $PORT docker environment variable (same as the port for the web ui)

### When are the endpoints updated

The endpoints are updated when objects in the API endpoints are changed.

### Location of the endpoints

In the container, these files are located under the API directory (default: `/tmp/api/`, configurable via `NETALERTX_API` environment variable). You can access them via the `/php/server/query_json.php?file=user_notifications.json` endpoint.

### Available endpoints

You can access the following files:

  | File name | Description |
  |----------------------|----------------------|
  | `notification_json_final.json` | The json version of the last notification (e.g. used for webhooks - [sample JSON](https://github.com/netalertx/NetAlertX/blob/main/front/report_templates/webhook_json_sample.json)). |
  | `table_devices.json` | All of the available Devices detected by the app. |
  | `table_plugins_events.json` | The list of the unprocessed (pending) notification events (plugins_events DB table). |
  | `table_plugins_history.json` | The list of notification events history. |
  | `table_plugins_objects.json` | The content of the plugins_objects table. Find more info on the [Plugin system here](https://docs.netalertx.com/PLUGINS)|
  | `language_strings.json` | The content of the language_strings table, which in turn is loaded from the plugins `config.json` definitions. |
  | `table_custom_endpoint.json` | A custom endpoint generated by the SQL query specified by the `API_CUSTOM_SQL` setting. |
  | `table_settings.json` | The content of the settings table. |
  | `app_state.json` | Contains the current application state. |


### JSON Data format

The endpoints starting with the `table_` prefix contain most, if not all, data contained in the corresponding database table. The common format for those is:

```JSON
{
  "data": [
        {
          "db_column_name": "data",
          "db_column_name2": "data2"
        },
        {
          "db_column_name": "data3",
          "db_column_name2": "data4"
        }
    ]
}

```

Example JSON of the `table_devices.json` endpoint with two Devices (database rows):

```JSON
{
  "data": [
        {
          "devMac": "Internet",
          "devName": "Net - Huawei",
          "devType": "Router",
          "devVendor": null,
          "devGroup": "Always on",
          "devFirstConnection": "2021-01-01 00:00:00",
          "devLastConnection": "2021-01-28 22:22:11",
          "devLastIP": "192.168.1.24",
          "devStaticIP": 0,
          "devPresentLastScan": 1,
          "devLastNotification": "2023-01-28 22:22:28.998715",
          "devIsNew": 0,
          "devParentMAC": "",
          "devParentPort": "",
          "devIcon": "globe"
        },
        {
          "devMac": "a4:8f:ff:aa:ba:1f",
          "devName": "Net - USG",
          "devType": "Firewall",
          "devVendor": "Ubiquiti Inc",
          "devGroup": "",
          "devFirstConnection": "2021-02-12 22:05:00",
          "devLastConnection": "2021-07-17 15:40:00",
          "devLastIP": "192.168.1.1",
          "devStaticIP": 1,
          "devPresentLastScan": 1,
          "devLastNotification": "2021-07-17 15:40:10.667717",
          "devIsNew": 0,
          "devParentMAC": "Internet",
          "devParentPort": 1,
          "devIcon": "shield-halved"
      }
    ]
}

```

## API Endpoint: Prometheus Exporter

* **Endpoint URL**: `/metrics`
* **Host**: (where NetAlertX exporter is running)
* **Port**: as configured in the `GRAPHQL_PORT` setting (`20212` by default)

---

### Example Output of the `/metrics` Endpoint

Below is a representative snippet of the metrics you may find when querying the `/metrics` endpoint for `netalertx`. It includes both aggregate counters and `device_status` labels per device.

```
netalertx_connected_devices 31
netalertx_offline_devices 54
netalertx_down_devices 0
netalertx_new_devices 0
netalertx_archived_devices 31
netalertx_favorite_devices 2
netalertx_my_devices 54

netalertx_device_status{device="Net - Huawei", mac="Internet", ip="1111.111.111.111", vendor="None", first_connection="2021-01-01 00:00:00", last_connection="2025-08-04 17:57:00", dev_type="Router", device_status="Online"} 1
netalertx_device_status{device="Net - USG", mac="74:ac:74:ac:74:ac", ip="192.168.1.1", vendor="Ubiquiti Networks Inc.", first_connection="2022-02-12 22:05:00", last_connection="2025-06-07 08:16:49", dev_type="Firewall", device_status="Archived"} 1
netalertx_device_status{device="Raspberry Pi 4 LAN", mac="74:ac:74:ac:74:74", ip="192.168.1.9", vendor="Raspberry Pi Trading Ltd", first_connection="2022-02-12 22:05:00", last_connection="2025-08-04 17:57:00", dev_type="Singleboard Computer (SBC)", device_status="Online"} 1
...
```

---

### Metrics Explanation

#### 1. Aggregate Device Counts

Metric names prefixed with `netalertx_` provide aggregated counts by device status:

* `netalertx_connected_devices`: number of devices currently connected
* `netalertx_offline_devices`: devices currently offline
* `netalertx_down_devices`: down/unreachable devices
* `netalertx_new_devices`: devices recently detected
* `netalertx_archived_devices`: archived devices
* `netalertx_favorite_devices`: user-marked favorite devices
* `netalertx_my_devices`: devices associated with the current user context

These numeric values give a high-level overview of device distribution.

#### 2. Per‑Device Status with Labels

Each individual device is represented by a `netalertx_device_status` metric, with descriptive labels:

* `device`: friendly name of the device
* `mac`: MAC address (or placeholder)
* `ip`: last recorded IP address
* `vendor`: manufacturer or "None" if unknown
* `first_connection`: timestamp when the device was first observed
* `last_connection`: most recent contact timestamp
* `dev_type`: device category or type
* `device_status`: current status (Online / Offline / Archived / Down / ...)

The metric value is always `1` (indicating presence or active state) and the combination of labels identifies the device.

---

### How to Query with `curl`

To fetch the metrics from the NetAlertX exporter:

```sh
curl 'http://<server_ip>:<GRAPHQL_PORT>/metrics' \
  -H 'Authorization: Bearer <API_TOKEN>' \
  -H 'Accept: text/plain'
```

Replace:

* `<server_ip>`: IP or hostname of the NetAlertX server
* `<GRAPHQL_PORT>`: port specified in your `GRAPHQL_PORT` setting  (default: `20212`)
* `<API_TOKEN>` your Bearer token from the `API_TOKEN` setting

---

### Summary

* **Endpoint**: `/metrics` provides both summary counters and per-device status entries.
* **Aggregate metrics** help monitor overall device states.
* **Detailed metrics** expose each device’s metadata via labels.
* **Use case**: feed into Prometheus for scraping, monitoring, alerting, or charting dashboard views.

### Prometheus Scraping Configuration

```yaml
scrape_configs:
  - job_name: 'netalertx'
    metrics_path: /metrics
    scheme: http
    scrape_interval: 60s
    static_configs:
      - targets: ['<server_ip>:<GRAPHQL_PORT>']
    authorization:
      type: Bearer
      credentials: <API_TOKEN>
```

### Grafana template

Grafana template sample: [Download json](./samples/API/Grafana_Dashboard.json)

## API Endpoint: /log files

This API endpoint retrieves files from the `/tmp/log` folder.

- Endpoint URL: `php/server/query_logs.php?file=<file name>`
- Host: `same as front end (web ui)`
- Port: `20211` or as defined by the $PORT docker environment variable (same as the port for the web ui)

| File                     | Description                                                   |
|--------------------------|---------------------------------------------------------------|
| `IP_changes.log`         | Logs of IP address changes                                    |
| `app.log`                | Main application log                                          |
| `app.php_errors.log`     | PHP error log                                                 |
| `app_front.log`          | Frontend application log                                      |
| `app_nmap.log`           | Logs of Nmap scan results                                     |
| `db_is_locked.log`       | Logs when the database is locked                              |
| `execution_queue.log`    | Logs of execution queue activities                            |
| `plugins/`               | Directory for temporary plugin-related files (not accessible) |
| `report_output.html`     | HTML report output                                            |
| `report_output.json`     | JSON format report output                                     |
| `report_output.txt`      | Text format report output                                     |
| `stderr.log`             | Logs of standard error output                                 |
| `stdout.log`             | Logs of standard output                                       |


## API Endpoint: /config files

To retrieve files from the `/data/config` folder.

- Endpoint URL: `php/server/query_config.php?file=<file name>`
- Host: `same as front end (web ui)`
- Port: `20211` or as defined by the $PORT docker environment variable (same as the port for the web ui)

| File                     | Description                                      |
|--------------------------|--------------------------------------------------|
| `devices.csv`            | Devices csv file                                 |
| `app.conf`               | Application config file                          |

