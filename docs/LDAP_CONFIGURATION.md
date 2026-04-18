# LDAP Authentication Configuration

NetAlertX supports LDAP and Active Directory for authentication as an alternative to the local password.

## Environment Variables

For security and automated deployments, you can configure LDAP entirely through environment variables. Environment variables **override** any settings saved in the UI/database.

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
| `LDAP_BIND_PASSWORD` | Password for the service account. Strongly recommended to set via environment or Docker secret. | |
| `LDAP_BASE_DN` | Base DN to search under (e.g., `ou=users,dc=example,dc=com`) | |
| `LDAP_USER_FILTER` | Search filter template. `{username}` is replaced at runtime. | `(uid={username})` |
| `LDAP_USERNAME_ATTRIBUTE` | LDAP attribute that holds the login name. | `uid` |

## Docker Compose Example

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

## Security Best Practices
1. Always enable `LDAP_TLS_VERIFY_CERT` in production to prevent Man-in-the-Middle attacks.
2. Mount your domain's CA certificate into the container via a Docker volume and set `LDAP_CA_CERT_PATH`.
3. Provide `LDAP_BIND_PASSWORD` via environment variables or Docker secrets (`/run/secrets/ldap_bind_password`) rather than the Web UI, which stores it in plaintext.
4. **Boot-Once Configuration:** To avoid exposing secrets like `LDAP_BIND_PASSWORD` permanently in your `docker-compose.yml` or `.env` file, you can set the environment variables for the initial deployment, log in, save the configuration in the Web UI (Settings > LDAP Authentication), and then remove the environment variables and restart the container. NetAlertX will safely fall back to the saved configuration.

## Common Configuration Examples

### OpenLDAP
* **`LDAP_PORT`**: `389` (or `636` for LDAPS)
* **`LDAP_USERNAME_ATTRIBUTE`**: `uid`
* **`LDAP_USER_FILTER`**: `(uid={username})`

### Active Directory
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
