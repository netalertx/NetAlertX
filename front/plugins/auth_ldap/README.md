## Overview

The LDAP Authentication plugin adds directory-backed login to NetAlertX. It supports both OpenLDAP and Microsoft Active Directory using a search-then-bind flow, and it can also use a direct bind format when your directory supports user principal names or predictable distinguished names.

### Features

- Authenticate users against LDAP or Active Directory from the NetAlertX login page
- Support OpenLDAP-style search filters and Active Directory `sAMAccountName` lookups
- Support LDAPS and StartTLS with optional custom CA bundle validation
- Allow anonymous search, service-account search, or direct bind authentication
- Provide a built-in Test action for validating user lookup configuration
- Optionally disable the local admin fallback for strict LDAP-only access

> [!WARNING]
> If local admin fallback remains enabled, the local `admin` account can still authenticate when LDAP is enabled. Change the local password and enable **Disable local admin account** if you want strict LDAP-only login.

### Quick Setup Guide

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
7. Optionally set **Test Username** and use the plugin **Test** action to validate the lookup path.
8. If you want LDAP to be mandatory, enable **Disable local admin account (Recommended)** after confirming LDAP login works.

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

#### Access Control and Testing Settings

- **Disable local admin account (Recommended)** (`LDAP_disable_local_admin`): Disables the local `admin` fallback and enforces LDAP-only login.
- **Test Username** (`LDAP_test_username`): Optional username used by the plugin Test action.
- **Command** (`LDAP_CMD`): Hidden internal test command used by NetAlertX when the plugin Test action is executed.

### Environment Variables

For automated deployments, LDAP can be configured entirely through environment variables. Environment variables **override** any settings saved in the UI/database.

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `LDAP_ENABLED` | Enable or disable LDAP authentication (`true` or `false`) | `false` |
| `LDAP_SERVER` | Hostname or IP address of the LDAP/AD server | |
| `LDAP_PORT` | TCP port for LDAP connections | `389` |
| `LDAP_USE_SSL` | Use LDAPS (TLS from the start). Mutually exclusive with StartTLS. (`true`/`false`) | `false` |
| `LDAP_USE_START_TLS` | Upgrade plain-text connection using STARTTLS. (`true`/`false`) | `false` |
| `LDAP_TLS_VERIFY_CERT` | Require a valid TLS certificate from the server. | `true` |
| `LDAP_CA_CERT_PATH` | Absolute path to a custom CA certificate bundle for validation (e.g. `/data/my-ca.pem`) | |
| `LDAP_DISABLE_LOCAL_ADMIN` | When `true`, completely disables the local fallback password. | `false` |
| `LDAP_DIRECT_BIND_FORMAT` | Format for direct binding (e.g., `{username}@example.com`). If set, bind DN and search filters are ignored. | |
| `LDAP_BIND_DN` | Distinguished Name of the read-only service account used to search for user entries. | |
| `LDAP_BIND_PASSWORD` | Password for the service account. | |
| `LDAP_BASE_DN` | Base DN to search under (e.g., `ou=users,dc=example,dc=com`) | |
| `LDAP_USER_FILTER` | Search filter template. `{username}` is replaced at runtime. | `(uid={username})` |
| `LDAP_USERNAME_ATTRIBUTE` | LDAP attribute that holds the login name. | `uid` |

### Docker Compose Example

```yaml
services:
  netalertx:
    image: netalertx:latest
    environment:
      - LDAP_ENABLED=true
      - LDAP_SERVER=ldap.example.com
      - LDAP_PORT=636
      - LDAP_USE_SSL=true
      - LDAP_TLS_VERIFY_CERT=true
      - LDAP_CA_CERT_PATH=/data/ca-certificates.crt
      - LDAP_BIND_DN=cn=readonly,dc=example,dc=com
      - LDAP_BIND_PASSWORD=super_secret_password
      - LDAP_BASE_DN=ou=users,dc=example,dc=com
      - LDAP_USER_FILTER=(uid={username})
      - LDAP_DISABLE_LOCAL_ADMIN=true
    volumes:
      - ./netalertx_data:/data
      # Mount the CA certificate into the container so NetAlertX can verify the LDAP server
      - ./my-company-ca.crt:/data/ca-certificates.crt:ro
```

### Common Configuration Examples

#### OpenLDAP
* **`LDAP_PORT`**: `389` (or `636` for LDAPS)
* **`LDAP_USERNAME_ATTRIBUTE`**: `uid`
* **`LDAP_USER_FILTER`**: `(uid={username})`

#### Active Directory
* **`LDAP_PORT`**: `389` (or `636` for LDAPS)
* **`LDAP_USERNAME_ATTRIBUTE`**: `sAMAccountName`
* **`LDAP_USER_FILTER`**: `(sAMAccountName={username})`

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

1. Configure the settings described above.
2. Save the settings.
3. Use the plugin **Test** action to verify lookup behavior before enforcing LDAP-only access.
4. Log in through the normal NetAlertX login page with LDAP credentials.

### Security Notes

- Always enable TLS certificate verification in production to prevent Man-in-the-Middle attacks.
- Prefer LDAPS or StartTLS for production deployments.
- If you use a private CA, place the CA bundle in a persistent path such as `/config/my-ca.pem` and set **CA Certificate Bundle Path**.
- The bind password is stored in `app.conf`. Treat the config file as sensitive data and restrict access accordingly.
- Enable **Disable local admin account** only after you have verified at least one LDAP login path works.

### Troubleshooting

#### LDAP server not configured

- Verify **Enable LDAP login** is on.
- Confirm **LDAP server** and **LDAP port** are saved correctly.

#### User not found

- Check **Base DN** and **User search filter**.
- Confirm the **Username attribute** matches your directory schema.
- Try the built-in **Test Username** with the plugin Test action.

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
- Release Date: April 2026