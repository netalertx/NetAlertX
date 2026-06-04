## 🧭 Responsibility Disclaimer

NetAlertX provides powerful tools for network scanning, presence detection, and automation. However, **it is up to you—the deployer—to ensure that your instance is properly secured**.

This includes (but is not limited to):
- Controlling who has access to the UI and API
- Following network and container security best practices
- Running NetAlertX only on networks where you have legal authorization
- Keeping your deployment up to date with the latest patches

> NetAlertX is not responsible for misuse, misconfiguration, or insecure deployments. Always test and secure your setup before exposing it to the outside world. Users interacting with the UI are treated as trusted actors within the deployment model.

# 🔐 Securing Your NetAlertX Instance

NetAlertX is a powerful network scanning and automation framework. With that power comes responsibility. **It is your responsibility to secure your deployment**, especially if you're running it outside a trusted local environment.

---

## ⚠️ TL;DR – Key Security Recommendations

- ✅ **NEVER expose NetAlertX directly to the internet without protection**
- ✅ Use a **VPN or Tailscale** to access remotely
- ✅ Enable **password protection** for the web UI
- ✅ Harden your container environment (e.g., no unnecessary privileges)
- ✅ Use **firewalls and IP whitelisting**
- ✅ Keep the software **updated**
- ✅ Limit the scope of **plugins and API keys**

---

## 🔗 Access Control with VPN (or Tailscale)

NetAlertX is designed to be run on **private LANs**, not the open internet.

**Recommended**: Use a VPN to access NetAlertX from remote locations.

### ✅ Tailscale (Easy VPN Alternative)

Tailscale sets up a private mesh network between your devices. It's fast to configure and ideal for NetAlertX.
👉 [Get started with Tailscale](https://tailscale.com/)

---

## 🔑 Web UI Password Protection

By default, NetAlertX does **not** require login. Before exposing the UI in any way:

1. Enable password protection:
   ```ini
   SETPWD_enable_password=true
   SETPWD_password=your_secure_password
   ```

2. Passwords are stored as SHA256 hashes

3. Default password (if not changed): 123456 — change it ASAP!


> To disable authenticated login, set `SETPWD_enable_password=false` in `app.conf`


---

## 🔥 Additional Security Measures

- **Firewall / Network Rules**
  Restrict UI/API access to trusted IPs only.

- **Limit Docker Capabilities**
  Avoid `--privileged`. Use `--cap-add=NET_RAW` and others **only if required** by your scan method.

- **Keep NetAlertX Updated**
  Regular updates contain bug fixes and security patches.

- **Plugin Permissions**
  Disable unused plugins. Only install from trusted sources.

- **Use Read-Only API Keys**
  When integrating NetAlertX with other tools, scope keys tightly.

---

## 🧱 Docker Hardening Tips

- Use `read-only` mount options where possible (`:ro`)
- Avoid running as `root` unless absolutely necessary
- Consider using `docker scan` or other container image vulnerability scanners
- Run with `--network host` **only on trusted networks** and only if needed for ARP-based scans

---

## 📣 Responsible Disclosure

If you discover a vulnerability or security concern, please report it **privately** to:

📧 [jokob@duck.com](mailto:jokob@duck.com?subject=NetAlertX%20Security%20Disclosure)

We take security seriously and will work to patch confirmed issues promptly. Your help in responsible disclosure is appreciated!

---

By following these recommendations, you can ensure your NetAlertX deployment is both powerful **and** secure.