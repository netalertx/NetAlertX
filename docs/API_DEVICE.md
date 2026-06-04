# Device API Endpoints

Manage a **single device** by its MAC address. Operations include retrieval, updates, deletion, resetting properties, and copying data between devices. All endpoints require **authorization** via Bearer token.

---

## 1. Retrieve Device Details

* **GET** `/device/<mac>`
  Fetch all details for a single device, including:

* Computed status (`devStatus`) → `On-line`, `Off-line`, or `Down`
* Session and event counts (`devSessions`, `devEvents`, `devDownAlerts`)
* Presence hours (`devPresenceHours`)
* Children devices (`devChildrenDynamic`) and NIC children (`devChildrenNicsDynamic`)

**Special case**: `mac=new` returns a template for a new device with default values.

**Response** (success):

```json
{
  "devMac": "AA:BB:CC:DD:EE:FF",
  "devName": "Net - Huawei",
  "devOwner": "Admin",
  "devType": "Router",
  "devVendor": "Huawei",
  "devStatus": "On-line",
  "devSessions": 12,
  "devEvents": 5,
  "devDownAlerts": 1,
  "devPresenceHours": 32,
  "devChildrenDynamic": [...],
  "devChildrenNicsDynamic": [...],
  ...
}
```

**Error Responses**:

* Device not found → HTTP 404
* Unauthorized → HTTP 403

**MCP Integration**: Available as `get_device_info` and `set_device_alias` tools. See [MCP Server Bridge API](API_MCP.md).

---

## 2. Update Device Fields

* **POST** `/device/<mac>`
  Create or update a device record.

> ⚠️ **Full-replace (PUT) semantics.** Every editable field is written on each call. Any field omitted from the payload is reset to its default (empty string or `0`). This matches how the frontend edit form works — it always sends the complete device state.
>
> To update a **single field** without affecting others, use [`POST /device/<mac>/update-column`](#7-update-a-single-column) instead.

**Request Body**:

```json
{
  "devName": "New Device",
  "devOwner": "Admin",
  "createNew": true
}
```

**Behavior**:

* If `createNew=true` → inserts a new device row
* Otherwise → **replaces all editable fields** on the existing device

**Response**:

```json
{
  "success": true
}
```

**Error Responses**:

* Unauthorized → HTTP 403

---

## 3. Delete a Device

* **DELETE** `/device/<mac>/delete`
  Deletes the device with the given MAC.

**Response**:

```json
{
  "success": true
}
```

**Error Responses**:

* Unauthorized → HTTP 403

---

## 4. Delete All Events for a Device

* **DELETE** `/device/<mac>/events/delete`
  Removes all events associated with a device.

**Response**:

```json
{
  "success": true
}
```

---

## 5. Reset Device Properties

* **POST** `/device/<mac>/reset-props`
  Resets the device's custom properties to default values.

**Request Body**: Optional JSON for additional parameters.

**Response**:

```json
{
  "success": true
}
```

---

## 6. Copy Device Data

* **POST** `/device/copy`
  Copy all data from one device to another. If a device exists with `macTo`, it is replaced.

**Request Body**:

```json
{
  "macFrom": "AA:BB:CC:DD:EE:FF",
  "macTo": "11:22:33:44:55:66"
}
```

**Response**:

```json
{
  "success": true,
  "message": "Device copied from AA:BB:CC:DD:EE:FF to 11:22:33:44:55:66"
}
```

**Error Responses**:

* Missing `macFrom` or `macTo` → HTTP 400
* Unauthorized → HTTP 403

---

## 7. Update a Single Column

* **POST** `/device/<mac>/update-column`
  Update exactly one field for a device without touching any other fields.

> ✅ **Partial-update (PATCH) semantics.** Only the specified column is written. All other fields are left unchanged. Use this for automation, integrations, and any workflow that needs to update a single attribute.
>
> To replace all fields at once (e.g. saving from the edit form), use [`POST /device/<mac>`](#2-update-device-fields).

Allowed `columnName` values: `devName`, `devOwner`, `devType`, `devVendor`, `devGroup`, `devLocation`, `devComments`, `devIcon`, `devFavorite`, `devAlertEvents`, `devAlertDown`, `devCanSleep`, `devSkipRepeated`, `devReqNicsOnline`, `devForceStatus`, `devParentMAC`, `devParentPort`, `devParentRelType`, `devSSID`, `devSite`, `devVlan`, `devStaticIP`, `devIsNew`, `devIsArchived`, `devCustomProps`.

**Request Body**:

```json
{
  "columnName": "devName",
  "columnValue": "Updated Device Name"
}
```

**Response** (success):

```json
{
  "success": true
}
```

**Error Responses**:

* Device not found → HTTP 404
* Missing `columnName` or `columnValue` → HTTP 400
* Unauthorized → HTTP 403

---

## 8. Lock / Unlock a Device Field

* **POST** `/device/<mac>/field/lock`
  Lock a field to prevent plugin overwrites, or unlock it to allow overwrites again.

**Request Body**:

```json
{
  "fieldName": "devName",
  "lock": true
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `fieldName` | string | ✅ | Field to lock/unlock (e.g. `devName`, `devVendor`) |
| `lock` | boolean | ❌ | `true` to lock, `false` to unlock (default when omitted) |

**Response** (success):

```json
{
  "success": true,
  "fieldName": "devName",
  "locked": true,
  "message": "Field devName locked"
}
```

**Error Responses**:

* Field does not support locking → HTTP 400
* Unauthorized → HTTP 403

---

## 9. Unlock / Clear Device Fields (Bulk)

* **POST** `/devices/fields/unlock`
  Unlock fields (clear `LOCKED`/`USER` sources) for one device, a list of devices, or all devices.

**Request Body**:

```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "fields": ["devName", "devVendor"],
  "clearAll": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `mac` | string or array | ❌ | Single MAC, list of MACs, or omit for all devices |
| `fields` | array of strings | ❌ | Fields to unlock. Omit to unlock all tracked fields |
| `clearAll` | boolean | ❌ | `true` clears all sources; `false` (default) clears only `LOCKED`/`USER` |

**Response** (success):

```json
{
  "success": true
}
```

**Error Responses**:

* `fields` is not a list → HTTP 400
* Unauthorized → HTTP 403

---

## 10. Set Device Alias

* **POST** `/device/<mac>/set-alias`
  Convenience wrapper to update the device display name (`devName`).

**Request Body**:

```json
{
  "alias": "My Router"
}
```

**Response** (success):

```json
{
  "success": true
}
```

**Error Responses**:

* Missing `alias` → HTTP 400
* Device not found → HTTP 404
* Unauthorized → HTTP 403

---

## Example `curl` Requests

**Get Device Details**:

```bash
curl -X GET "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF" \
  -H "Authorization: Bearer <API_TOKEN>"
```

**Update Device Fields**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"devName": "New Device Name"}'
```

**Delete Device**:

```bash
curl -X DELETE "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF/delete" \
  -H "Authorization: Bearer <API_TOKEN>"
```

**Copy Device Data**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/device/copy" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"macFrom":"AA:BB:CC:DD:EE:FF","macTo":"11:22:33:44:55:66"}'
```

**Update Single Column**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF/update-column" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"columnName":"devName","columnValue":"Updated Device"}'
```

**Lock a Field**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF/field/lock" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"fieldName":"devName","lock":true}'
```

**Unlock Fields (all devices)**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/devices/fields/unlock" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"fields":["devName","devVendor"]}'
```

**Set Device Alias**:

```bash
curl -X POST "http://<server_ip>:<GRAPHQL_PORT>/device/AA:BB:CC:DD:EE:FF/set-alias" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"alias":"My Router"}'
```

