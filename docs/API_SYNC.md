# Sync API Endpoint

---

The `/sync` endpoint is used by the **SYNC plugin** to synchronize data between multiple NetAlertX instances (e.g., from a node to a hub). It supports both **GET** and **POST** requests.

#### 9.1 GET `/sync`

Fetches data from a node to the hub. The data is returned as a **base64-encoded JSON file**.

**Example Request:**

```sh
curl 'http://<server>:<GRAPHQL_PORT>/sync' \
  -H 'Authorization: Bearer <API_TOKEN>'
```

**Response Example:**

```json
{
  "node_name": "NODE-01",
  "status": 200,
  "message": "OK",
  "data_base64": "eyJkZXZpY2VzIjogW3siZGV2TWFjIjogIjAwOjExOjIyOjMzOjQ0OjU1IiwiZGV2TmFtZSI6ICJEZXZpY2UgMSJ9XSwgImNvdW50Ijog1fQ==",
  "timestamp": "2025-08-24T10:15:00+10:00"
}
```

**Notes:**

* `data_base64` contains the full JSON data encoded in Base64.
* `node_name` corresponds to the `SYNC_node_name` setting on the node.
* Errors (e.g., missing file) return HTTP 500 with an error message.

---

#### 9.2 POST `/sync`

The **POST** endpoint is used by nodes to **send data to the hub**. The hub expects the data as **form-encoded fields** (application/x-www-form-urlencoded or multipart/form-data). The hub then stores the data in the plugin log folder for processing.

#### Required Fields

| Field       | Type              | Description                                                                                                                                                                  |
| ----------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data`      | string            | The payload from the plugin or devices. Typically **plain text**, **JSON**, or **encrypted Base64** data. In your Python script, `encrypt_data()` is applied before sending. |
| `node_name` | string            | The name of the node sending the data. Matches the node’s `SYNC_node_name` setting. Used to generate the filename on the hub.                                                |
| `plugin`    | string            | The name of the plugin sending the data. Determines the filename prefix (`last_result.<plugin>...`).                                                                         |
| `file_path` | string (optional) | Path of the local file being sent. Used only for logging/debugging purposes on the hub; **not required for processing**.                                                     |

---

### How the Hub Processes the POST Data

1. **Receives the data** and validates the API token.
2. **Stores the raw payload** in:

```
INSTALL_PATH/log/plugins/last_result.<plugin>.encoded.<node_name>.<sequence>.log
```

* `<plugin>` → plugin name from the POST request.
* `<node_name>` → node name from the POST request.
* `<sequence>` → incremented number for each submission.

3. **Decodes / decrypts the data** if necessary (Base64 or encrypted) before processing.
4. **Processes JSON payloads** (e.g., device info) to:

   * Avoid duplicates by tracking `devMac`.
   * Add metadata like `devSyncHubNode`.
   * Insert new devices into the database.
5. **Renames files** to indicate they have been processed:

```
processed_last_result.<plugin>.<node_name>.<sequence>.log
```

---

### Example POST Payload

If a node is sending device data:

```bash
curl -X POST 'http://<hub>:<PORT>/sync' \
  -H 'Authorization: Bearer <API_TOKEN>' \
  -F 'data={"data":[{"devMac":"00:11:22:33:44:55","devName":"Device 1","devVendor":"Vendor A","devLastIP":"192.168.1.10"}]}' \
  -F 'node_name=NODE-01' \
  -F 'plugin=SYNC'
```

* The `data` field contains JSON with a **`data` array**, where each element is a **device object** or **plugin data object**.
* The `plugin` and `node_name` fields allow the hub to **organize and store the file correctly**.
* The data is only processed if the relevant plugins are enabled and run on the target server.

---

### Key Notes

* **Always use the same `plugin` and `node_name` values** for consistent storage.
* **Encrypted data**: The Python script uses `encrypt_data()` before sending, and the hub decodes it before processing.
* **Sequence numbers**: Every submission generates a new sequence, preventing overwriting previous data.
* **Form-encoded**: The hub expects `multipart/form-data` (cURL `-F`) or `application/x-www-form-urlencoded`.

**Storage Details:**

* Data is stored under `INSTALL_PATH/log/plugins` with filenames following the pattern:

```
last_result.<plugin>.encoded.<node_name>.<sequence>.log
```

* Both encoded and decoded files are tracked, and new submissions increment the sequence number.
* If storing fails, the API returns HTTP 500 with an error message.
* The data is only processed if the relevant plugins are enabled and run on the target server.

---

#### 9.3 Notes and Best Practices

* **Authorization Required** – Both GET and POST require a valid API token.
* **Data Integrity** – Ensure that `node_name` and `plugin` are consistent to avoid overwriting files.
* **Monitoring** – An in-app log entry is written via `write_notification` whenever data is sent or received, which can be used for auditing.
* **Use Case** – Typically used in multi-node deployments to consolidate device and event data on a central hub.

---

#### 9.4 Hub Device-Write Behavior (`SYNC_BEHAVIOR`)

The `SYNC_BEHAVIOR` setting controls how the hub writes devices received from nodes (Mode 3 — RECEIVE). It only affects the hub.

| Value | Default? | Writes to Devices |
|---|---|---|
| `copy-new` | ✅ | New MACs only (INSERT OR IGNORE) |
| `carbon-copy` | | All MACs every sync (UPSERT) |
| `hub-defaults` | | None — hub pipeline handles it |

For full details and per-mode behaviour, see [SYNC plugin README — Hub Device-Write Behavior](https://github.com/netalertx/NetAlertX/tree/main/front/plugins/sync/README.md#hub-device-write-behavior-sync_behavior).

