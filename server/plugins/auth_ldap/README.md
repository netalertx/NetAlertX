## Overview

The LDAP Authentication plugin adds directory-backed login to NetAlertX. It supports both OpenLDAP and Microsoft Active Directory using a search-then-bind flow, and it can also use a direct bind format when your directory supports user principal names or predictable distinguished names.

### Features

- Authenticate users against LDAP or Active Directory from the NetAlertX login page
- Support OpenLDAP-style search filters and Active Directory `sAMAccountName` lookups
- Support LDAPS and StartTLS with optional custom CA bundle validation
- Allow anonymous search, service-account search, or direct bind authentication
- Optionally disable the local admin fallback for strict LDAP-only access
- Built-in brute-force rate limiting on login attempts

> [!WARNING]
> If local admin fallback remains enabled, the local `admin` account can still authenticate when LDAP is enabled. Change the local password and enable **Disable local admin account** if you want strict LDAP-only login.

### Quick Setup Guide

> [!NOTE]
> NetAlertX does not define individual environment variables for LDAP configuration. All LDAP options are standard application settings configured through the Web UI (**Settings > LDAP Authentication**). To initialize or override settings headlessly in automated or containerized environments, see [Headless / Automated Configuration (`APP_CONF_OVERRIDE`)](#headless--automated-configuration-app_conf_override).

1. Open **Settings** and navigate to **LDAP Authentication**.
2. Enable **Enable LDAP login**.
3. Enter the LDAP server hostname and port.
4. Choose one transport mode:
   - **Use LDAPS (SSL)** for TLS from connect time, usually port `636`
   - **Use StartTLS** for upgrading a plain LDAP connection, usually port `389`
5. Choose one bind strategy:
   - **Search then bind**: configure **Bind DN**, **Bind password**, **Base DN**, and **User search filter**
   - **Direct bind**: set **Direct Bind Format** and leave search-specific fields unused
6. Set **Username attribute** to match your directory, usually `uid` for OpenLDAP or `sAMAccountName` for Active Directory.
7. If you want LDAP to be mandatory, enable **Disable local admin account (Recommended)** after confirming LDAP login works.

#### Required Settings

- **Enable LDAP login** (`LDAP_enabled`): Turns on LDAP-backed authentication and shows the username field on the login form.
- **LDAP server** (`LDAP_server`): Hostname or IP address of the LDAP or Active Directory server.
- **LDAP port** (`LDAP_port`): Directory port. Typical values are `389` for LDAP or StartTLS and `636` for LDAPS.

#### Authentication Mode Settings

- **Direct Bind Format (Optional)** (`LDAP_direct_bind_format`): Optional user DN or UPN template such as `{username}@example.com` or `uid={username},ou=users,dc=example,dc=com`. When this is set, search settings are ignored.
- **Bind DN (service account)** (`LDAP_bind_dn`): Read-only service account DN used for the initial search bind. Leave empty for anonymous bind if your directory allows it.
- **Bind password** (`LDAP_bind_password`): Password for the service account.
- **Base DN** (`LDAP_base_dn`): Search root used to find the authenticating user.
- **User search filter** (`LDAP_user_filter`): Search filter template containing `{username}`. Example OpenLDAP filter: `(uid={username})`. Example Active Directory filter: `(sAMAccountName={username})`.
- **Username attribute** (`LDAP_username_attribute`): Attribute that stores the login name.

#### TLS and Certificate Settings

- **Use LDAPS (SSL)** (`LDAP_use_ssl`): Connect using TLS immediately.
- **Use StartTLS** (`LDAP_use_start_tls`): Upgrade a plain LDAP connection to TLS.
- **Verify TLS Certificate** (`LDAP_tls_verify_cert`): Require a valid server certificate. Disable only for temporary testing.
- **CA Certificate Bundle Path** (`LDAP_ca_cert_path`): Absolute path to a CA bundle when your directory uses a private CA.

#### Access Control Settings

- **Disable local admin account (Recommended)** (`LDAP_disable_local_admin`): Disables the local `admin` fallback and enforces LDAP-only login.

### Headless / Automated Configuration (`APP_CONF_OVERRIDE`)

For automated and containerized deployments, all NetAlertX settings (including LDAP) can be initialized or overridden using the standard `APP_CONF_OVERRIDE` environment variable containing a JSON dictionary of setting keys and values. Individual setting environment variables are not supported to avoid duplicating configuration mechanisms.

| Setting Key | Description | Default |
|-------------|-------------|---------|
| `LDAP_enabled` | Enable or disable LDAP authentication (`true` or `false`) | `false` |
| `LDAP_server` | Hostname or IP address of the LDAP/AD server | `""` |
| `LDAP_port` | TCP port for LDAP connections | `389` |
| `LDAP_use_ssl` | Use LDAPS (TLS from the start). Mutually exclusive with StartTLS. (`true`/`false`) | `false` |
| `LDAP_use_start_tls` | Upgrade plain-text connection using STARTTLS. (`true`/`false`) | `false` |
| `LDAP_tls_verify_cert` | Require a valid TLS certificate from the server. | `true` |
| `LDAP_ca_cert_path` | Absolute path to a custom CA certificate bundle for validation (e.g. `/data/my-ca.pem`) | `""` |
| `LDAP_disable_local_admin` | When `true`, completely disables the local fallback password. | `false` |
| `LDAP_direct_bind_format` | Format for direct binding (e.g., `{username}@example.com`). If set, bind DN and search filters are ignored. | `""` |
| `LDAP_bind_dn` | Distinguished Name of the read-only service account used to search for user entries. | `""` |
| `LDAP_bind_password` | Password for the service account. | `""` |
| `LDAP_base_dn` | Base DN to search under (e.g., `ou=users,dc=example,dc=com`) | `""` |
| `LDAP_user_filter` | Search filter template. `{username}` is replaced at runtime. | `(uid={username})` |
| `LDAP_username_attribute` | LDAP attribute that holds the login name. | `uid` |

### Docker Compose Example

```yaml
services:
  netalertx:
    image: netalertx:latest
    environment:
      - APP_CONF_OVERRIDE={"LDAP_enabled":true,"LDAP_server":"ldap.example.com","LDAP_port":636,"LDAP_use_ssl":true,"LDAP_tls_verify_cert":true,"LDAP_ca_cert_path":"/data/ca-certificates.crt","LDAP_bind_dn":"cn=readonly,dc=example,dc=com","LDAP_bind_password":"super_secret_password","LDAP_base_dn":"ou=users,dc=example,dc=com","LDAP_user_filter":"(uid={username})","LDAP_disable_local_admin":true}
    volumes:
      - ./netalertx_data:/data
      # Mount the CA certificate into the container so NetAlertX can verify the LDAP server
      - ./my-company-ca.crt:/data/ca-certificates.crt:ro
```

### Common Configuration Examples

#### OpenLDAP
* **`LDAP_port`**: `389` (or `636` for LDAPS)
* **`LDAP_username_attribute`**: `uid`
* **`LDAP_user_filter`**: `(uid={username})`

#### Active Directory
* **`LDAP_port`**: `389` (or `636` for LDAPS)
* **`LDAP_username_attribute`**: `sAMAccountName`
* **`LDAP_user_filter`**: `(sAMAccountName={username})`

**Advanced Active Directory Filter Examples:**
* Require user to be in a specific group (e.g., `NetAlertX`):
  ```text
  (&(memberOf=CN=NetAlertX,OU=Groups,DC=example,DC=com)(sAMAccountName={username}))
  ```
* Restrict login to a specific user only (e.g., `my_username`):
  ```text
  (&(sAMAccountName=my_username)(sAMAccountName={username}))
  ```

### Usage

1. Configure the settings described above in the UI or via `APP_CONF_OVERRIDE`.
2. Save the settings.
3. Test logging in through the NetAlertX login page with an LDAP user while the local admin fallback is still active.
4. Once verified, enable **Disable local admin account** if desired.

### Security Notes

- Always enable TLS certificate verification in production to prevent Man-in-the-Middle attacks.
- Prefer LDAPS or StartTLS for production deployments.
- If you use a private CA, place the CA bundle in a persistent path such as `/config/my-ca.pem` and set **CA Certificate Bundle Path**.
- The bind password is stored in `app.conf`. Treat the config file as sensitive data and restrict access accordingly.
- Enable **Disable local admin account** only after you have verified at least one LDAP login path works.

#### Brute-Force Rate Limiting
To protect against automated password guessing and credential stuffing, the `/api/auth/login` endpoint enforces per-client-IP in-memory rate limiting defined in `server/api_server/api_server_start.py`:
- **Maximum failed attempts:** 5 failed attempts (`_MAX_FAILED_ATTEMPTS = 5`)
- **Lockout window:** 300 seconds / 5 minutes (`_LOCKOUT_WINDOW_SECONDS = 300`)
- **Lockout response:** When rate-limited, the endpoint rejects the request with HTTP 429 (`Too Many Requests`) and payload `{"success": false, "message": "Too many failed attempts. Try again later.", "error": "Too many failed attempts. Try again later."}`.
- **Reset on success:** Successful logins immediately reset the failure counter and clear the lockout record for that client IP.
- **Client IP resolution:** Client IP is determined from the first entry of the `X-Forwarded-For` header or `request.remote_addr`.

### Troubleshooting

#### LDAP server not configured

- Verify **Enable LDAP login** is on.
- Confirm **LDAP server** and **LDAP port** are saved correctly.

#### User not found

- Check **Base DN** and **User search filter**.
- Confirm the **Username attribute** matches your directory schema.

#### TLS or certificate failures

- Make sure **Use LDAPS (SSL)** and **Use StartTLS** are not both enabled at the same time.
- Confirm the CA bundle path is valid when certificate verification is enabled.
- Test with certificate verification enabled before considering temporary relaxation for lab environments.

#### Login falls back to local admin

- This is expected when **Disable local admin account** is off.
- Turn it on only after LDAP login succeeds consistently.

### Technical Notes

- Plugin type: `system`
- Data source: `template`
- Login flow: search then bind, or direct bind if `LDAP_direct_bind_format` is set

### Version

- Version: 1.0.0
- Author: NetAlertX contributors
- Release Date: October 2026
