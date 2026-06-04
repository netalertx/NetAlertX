# Events API Endpoints

The Events API provides access to **device event logs**, allowing creation, retrieval, deletion, and summary of events over time.

---

## Endpoints

### 1. Create Event

* **POST** `/events/create/<mac>`
  Create an event for a device identified by its MAC address.

**Request Body** (JSON):

```json
{
  "ip": "192.168.1.10",
  "event_type": "Device Down",
  "additional_info": "Optional info about the event",
  "pending_alert": 1,
  "event_time": "2025-08-24T12:00:00Z"
}
```

* **Parameters**:

  * `ip` (string, optional): IP address of the device
  * `event_type` (string, optional): Type of event (default `"Device Down"`)
  * `additional_info` (string, optional): Extra information
  * `pending_alert` (int, optional): 1 if alert email is pending (default 1)
  * `event_time` (ISO datetime, optional): Event timestamp; defaults to current time

**Response** (JSON):

```json
{
  "success": true,
  "message": "Event created for 00:11:22:33:44:55"
}
```

---

### 2. Get Events

* **GET** `/events`
  Retrieve all events, optionally filtered by MAC address:

```
/events?mac=<mac>
```

**Response**:

```json
{
  "success": true,
  "events": [
    {
      "eveMac": "00:11:22:33:44:55",
      "eveIp": "192.168.1.10",
      "eveDateTime": "2025-08-24T12:00:00Z",
      "eveEventType": "Device Down",
      "eveAdditionalInfo": "",
      "evePendingAlertEmail": 1
    }
  ]
}
```

---

### 3. Delete Events

* **DELETE** `/events/<mac>` → Delete events for a specific MAC
* **DELETE** `/events` → Delete **all** events
* **DELETE** `/events/<days>` → Delete events older than N days

**Response**:

```json
{
  "success": true,
  "message": "Deleted events older than <days> days"
}
```

---

### 4. Get Recent Events

* **GET** `/events/recent` → Get events from the last 24 hours
* **GET** `/events/<hours>` → Get events from the last N hours

**Response** (JSON):

```json
{
  "success": true,
  "hours": 24,
  "count": 5,
  "events": [
    {
      "eveDateTime": "2025-12-07 12:00:00",
      "eveEventType": "New Device",
      "eveMac": "AA:BB:CC:DD:EE:FF",
      "eveIp": "192.168.1.100",
      "eveAdditionalInfo": "Device detected"
    }
  ]
}
```

---

### 5. Get Latest Events

* **GET** `/events/last`
  Get the 10 most recent events.

**Response** (JSON):

```json
{
  "success": true,
  "count": 10,
  "events": [
    {
      "eveDateTime": "2025-12-07 12:00:00",
      "eveEventType": "Device Down",
      "eveMac": "AA:BB:CC:DD:EE:FF"
    }
  ]
}
```

---

### 6. Event Totals Over a Period

* **GET** `/sessions/totals?period=<period>`
  Return event and session totals over a given period.

**Query Parameters**:

| Parameter | Description                                                                      |
| --------- | -------------------------------------------------------------------------------- |
| `period`  | Time period for totals, e.g., `"7 days"`, `"1 month"`, `"1 year"`, `"100 years"` |

**Sample Response** (JSON Array):

```json
[120, 85, 5, 10, 3, 7]
```

**Meaning of Values**:

1. Total events in the period
2. Total sessions
3. Missing sessions
4. Voided events (`eveEventType LIKE 'VOIDED%'`)
5. New device events (`eveEventType LIKE 'New Device'`)
6. Device down events (`eveEventType LIKE 'Device Down'`)

---

## MCP Tools

Event endpoints are available as **MCP Tools** for AI assistant integration:
- `get_recent_alerts`, `get_last_events`

📖 See [MCP Server Bridge API](API_MCP.md) for AI integration details.

---

## Notes

* All endpoints require **authorization** (Bearer token). Unauthorized requests return HTTP 403:

```json
{
  "success": false,
  "message": "ERROR: Not authorized",
  "error": "Forbidden"
}
```

* Events are stored in the **Events table** with the following fields:
  `eveMac`, `eveIp`, `eveDateTime`, `eveEventType`, `eveAdditionalInfo`, `evePendingAlertEmail`.

* Event creation automatically logs activity for debugging.

---

## Example `curl` Requests

**Create Event**:

```sh
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/events/create/00:11:22:33:44:55" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{
    "ip": "192.168.1.10",
    "event_type": "Device Down",
    "additional_info": "Power outage",
    "pending_alert": 1
  }'
```

**Get Events for a Device**:

```sh
curl "http://<server_ip>:<GRAPHQL_PORT>/events?mac=00:11:22:33:44:55" \
  -H "Authorization: Bearer <API_TOKEN>"
```

**Delete Events Older Than 30 Days**:

```sh
curl -X DELETE "http://<server_ip>:<GRAPHQL_PORT>/events/30" \
  -H "Authorization: Bearer <API_TOKEN>"
```

**Get Event Totals for 7 Days**:

```sh
curl "http://<server_ip>:<GRAPHQL_PORT>/sessions/totals?period=7 days" \
  -H "Authorization: Bearer <API_TOKEN>"
```
