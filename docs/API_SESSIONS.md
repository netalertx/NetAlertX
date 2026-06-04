# Sessions API Endpoints

Track and manage device connection sessions. Sessions record when a device connects or disconnects on the network.

### Create a Session

* **POST** `/sessions/create` → Create a new session for a device

  **Request Body:**

  ```json
  {
    "mac": "AA:BB:CC:DD:EE:FF",
    "ip": "192.168.1.10",
    "start_time": "2025-08-01T10:00:00",
    "end_time": "2025-08-01T12:00:00",      // optional
    "event_type_conn": "Connected",         // optional, default "Connected"
    "event_type_disc": "Disconnected"       // optional, default "Disconnected"
  }
  ```

  **Response:**

  ```json
  {
    "success": true,
    "message": "Session created for MAC AA:BB:CC:DD:EE:FF"
  }
  ```

#### `curl` Example

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/sessions/create" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "mac": "AA:BB:CC:DD:EE:FF",
    "ip": "192.168.1.10",
    "start_time": "2025-08-01T10:00:00",
    "end_time": "2025-08-01T12:00:00",
    "event_type_conn": "Connected",
    "event_type_disc": "Disconnected"
  }'

```

---

### Delete Sessions

* **DELETE** `/sessions/delete` → Delete all sessions for a given MAC

  **Request Body:**

  ```json
  {
    "mac": "AA:BB:CC:DD:EE:FF"
  }
  ```

  **Response:**

  ```json
  {
    "success": true,
    "message": "Deleted sessions for MAC AA:BB:CC:DD:EE:FF"
  }
  ```

#### `curl` Example

```bash
curl -X DELETE "http://<server_ip>:<GRAPHQL_PORT>/sessions/delete" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "mac": "AA:BB:CC:DD:EE:FF"
  }'
```

---

### List Sessions

* **GET** `/sessions/list` → Retrieve sessions optionally filtered by device and date range

  **Query Parameters:**

  * `mac` (optional) → Filter by device MAC address
  * `start_date` (optional) → Filter sessions starting from this date (`YYYY-MM-DD`)
  * `end_date` (optional) → Filter sessions ending by this date (`YYYY-MM-DD`)

  **Example:**

  ```
  /sessions/list?mac=AA:BB:CC:DD:EE:FF&start_date=2025-08-01&end_date=2025-08-21
  ```

  **Response:**

  ```json
  {
    "success": true,
    "sessions": [
      {
        "sesMac": "AA:BB:CC:DD:EE:FF",
        "sesDateTimeConnection": "2025-08-01 10:00",
        "sesDateTimeDisconnection": "2025-08-01 12:00",
        "sesDuration": "2h 0m",
        "sesIp": "192.168.1.10",
        "sesAdditionalInfo": ""
      }
    ]
  }
  ```
#### `curl` Example

**get sessions for mac**

```bash
curl -X GET "http://<server_ip>:<GRAPHQL_PORT>/sessions/list?mac=AA:BB:CC:DD:EE:FF&start_date=2025-08-01&end_date=2025-08-21" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json"
```

---

### Calendar View of Sessions

* **GET** `/sessions/calendar` → View sessions in calendar format

  **Query Parameters:**

  * `start` → Start date (`YYYY-MM-DD`)
  * `end` → End date (`YYYY-MM-DD`)

  **Example:**

  ```
  /sessions/calendar?start=2025-08-01&end=2025-08-21
  ```

  **Response:**

  ```json
  {
    "success": true,
    "sessions": [
      {
        "resourceId": "AA:BB:CC:DD:EE:FF",
        "title": "",
        "start": "2025-08-01T10:00:00",
        "end": "2025-08-01T12:00:00",
        "color": "#00a659",
        "tooltip": "Connection: 2025-08-01 10:00\nDisconnection: 2025-08-01 12:00\nIP: 192.168.1.10",
        "className": "no-border"
      }
    ]
  }
  ```

#### `curl` Example

```bash
curl -X GET "http://<server_ip>:<GRAPHQL_PORT>/sessions/calendar?start=2025-08-01&end=2025-08-21" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json"
```

---

### Device Sessions

* **GET** `/sessions/<mac>` → Retrieve sessions for a specific device

  **Query Parameters:**

  * `period` → Period to retrieve sessions (`1 day`, `7 days`, `1 month`, etc.)
    Default: `1 day`

  **Example:**

  ```
  /sessions/AA:BB:CC:DD:EE:FF?period=7 days
  ```

  **Response:**

  ```json
  {
    "success": true,
    "sessions": [
      {
        "sesMac": "AA:BB:CC:DD:EE:FF",
        "sesDateTimeConnection": "2025-08-01 10:00",
        "sesDateTimeDisconnection": "2025-08-01 12:00",
        "sesDuration": "2h 0m",
        "sesIp": "192.168.1.10",
        "sesAdditionalInfo": ""
      }
    ]
  }
  ```

#### `curl` Example

```bash
curl -X GET "http://<server_ip>:<GRAPHQL_PORT>/sessions/AA:BB:CC:DD:EE:FF?period=7%20days" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json"
```

---

### Session Events Summary

* **GET** `/sessions/session-events` → Retrieve a summary of session events

  **Query Parameters:**

  * `type` → Event type (`all`, `sessions`, `missing`, `voided`, `new`, `down`)
    Default: `all`
  * `period` → Period to retrieve events (`7 days`, `1 month`, etc.)
  * `page` → Page number, 1-based (default: `1`)
  * `limit` → Rows per page, max 1000 (default: `100`)
  * `search` → Free-text search filter across all columns
  * `sortCol` → Column index to sort by, 0-based (default: `0`)
  * `sortDir` → Sort direction: `asc` or `desc` (default: `desc`)

  **Example:**

  ```
  /sessions/session-events?type=all&period=7 days&page=1&limit=25&sortCol=3&sortDir=desc
  ```

  **Response:**

  ```json
  {
    "data": [...],
    "total": 150,
    "recordsFiltered": 150
  }
  ```

  | Field             | Type | Description                                       |
  | ----------------- | ---- | ------------------------------------------------- |
  | `data`            | list | Paginated rows (each row is a list of values).    |
  | `total`           | int  | Total rows before search filter.                  |
  | `recordsFiltered` | int  | Total rows after search filter (before paging).   |

#### `curl` Example

```bash
curl -X GET "http://<server_ip>:<GRAPHQL_PORT>/sessions/session-events?type=all&period=7%20days" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Accept: application/json"
```