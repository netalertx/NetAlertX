## Documentation overview

<details>
  <summary>:information_source: In the app hover over settings or fields/labels or click blue in-app ❔ (question-mark) icons to get to relevant documentation pages.</summary>

  ![In-app help](./img/GENERAL/in-app-help.png)

</details>

There is also an in-app Help / FAQ section that should be answering frequently asked questions.

### 📥 Installation

#### 🐳 Docker (Fully supported)

- The main installation method is as a [docker container - follow these instructions here](./DOCKER_INSTALLATION.md).

#### 💻 Bare-metal / On-server (Experimental/community supported 🧪)

- [(Experimental 🧪) On-hardware instructions](./HW_INSTALL.md)

- Alternative bare-metal install forks:
  - [leiweibau's fork](https://github.com/leiweibau/Pi.Alert/) (maintained)
  - [pucherot's original code](https://github.com/pucherot/Pi.Alert/) (un-maintained)

### 📚 Table of contents

#### 📥 Initial Setup

- [Synology Guide](./SYNOLOGY_GUIDE.md)
- [Subnets and VLANs configuration for arp-scan](./SUBNETS.md)
- [Scanning Remote Networks](./REMOTE_NETWORKS.md)
- [SMTP server config](./SMTP.md)
- [Custom Icon configuration and support](./ICONS.md)
- [Notifications](./NOTIFICATIONS.md)
- [Better name resolution with Reverse DNS](./REVERSE_DNS.md)
- [Network treemap configuration](./NETWORK_TREE.md)
- [Backups](./BACKUPS.md)
- [Plugins overview](/docs/PLUGINS.md)

#### 🐛 Debugging help & tips

- [Debugging tips](./DEBUG_TIPS.md)
- [Debugging UI not showing](./WEB_UI_PORT_DEBUG.md)
- [Invalid JSON errors debug help](./DEBUG_INVALID_JSON.md)
- [Troubleshooting Plugins](./DEBUG_PLUGINS.md)
- [File Permissions](./FILE_PERMISSIONS.md)
- [Performance tips](./PERFORMANCE.md)

#### 🔝 Popular/Suggested

- [Home Assistant](./HOME_ASSISTANT.md)
- [Bulk edit devices](./DEVICES_BULK_EDITING.md)

#### ⚙ System Management

- [Manage devices (legacy docs)](./DEVICE_MANAGEMENT.md)
- [Random MAC/MAC icon meaning (legacy docs)](./RANDOM_MAC.md)

#### 🔎 Examples

- [N8N webhook example](./WEBHOOK_N8N.md)

#### ♻ Misc

- [Reverse Proxy](./REVERSE_PROXY.md)
- [Installing Updates](./UPDATES.md)
- [Setting up Authelia](./AUTHELIA.md) (DRAFT)

#### 👩‍💻For Developers👨‍💻

- [Setting up your DEV environment](./DEV_ENV_SETUP.md)
- [Server APP code structure](/server/README.md)
- [Database structure](./DATABASE.md)
- [API endpoints details](./API.md)
- [Plugin development guide](./PLUGINS_DEV.md)
- [Settings system](./SETTINGS_SYSTEM.md)
- [New Version notifications](./VERSIONS.md)
- [Frontend development tips](./FRONTEND_DEVELOPMENT.md)
- [Webhook secrets](./WEBHOOK_SECRET.md)

Feel free to suggest or submit new docs via a PR.

## 👨‍💻 Development priorities

Priorities from highest to lowest:

* 🔼 Fixing core functionality bugs not solvable with workarounds
* 🔵 New core functionality unlocking other opportunities (e.g.: plugins)
* 🔵 Refactoring enabling faster implementation of future functionality
* 🔽 (low) UI functionality & improvements (PRs welcome 😉)

Design philosophy: Focus on core functionality and leverage existing apps and tools to make NetAlertX integrate into other workflows.

Examples:

    1. Supporting apprise makes more sense than implementing multiple individual notification gateways
    2. Implementing regular expression support across settings for validation makes more sense than validating one setting with a specific expression.

UI-specific requests are a low priority as the framework picked by the original developer is not very extensible (and afaik doesn't support components) and has limited mobile support. Also, I argue the value proposition is smaller than working on something else.

Feel free to submit PRs if interested. try to **keep the PRs small/on-topic** so they are easier to review and approve.

That being said, I'd reconsider if more people and or recurring sponsors file a request 😉.

## 🙏 Feature requests

Please be as detailed as possible with **workarounds** you considered and why a native feature is the better way. This gives me better context and will make it more likely to be implemented. Ideally, a feature request should be in the format "I want to be able to do XYZ so that ZYX. I considered these approaches XYZ".

## ➕ Pull requests (PRs)

If you submit a PR please:

1. Check that your changes are backward compatible with existing installations and with a blank setup.
2. Existing features should always be preserved.
3. Keep the PR small, on-topic and don't change code that is not necessary for the PR to work
4. New features code should ideally be re-usable for different purposes, not for a very narrow use case.
5. New functionality should ideally be implemented via the Plugins system, if possible.

Suggested test cases:

- Blank setup with no DB or config
- Existing DB / config
- Sending a notification (e. g. Delete a device and wait for a scan to run) and testing all notification gateways, especially:
   - Email, Apprise (e.g. via Telegram), webhook (e.g. via Discord), MQTT (e.g. via Home Assistant)
- Saving settings
- Test a couple of plugins
- Check the Error log for anything unusual

Some additional context:

* Permanent settings/config is stored in the `app.conf` file
* Currently temporary (session?) settings are stored in the `Parameters` DB table as key-value pairs. This table is wiped during a container rebuild/restart and its values are re-initialized from cookies/session data from the browser.

## 🐛 Submitting an issue or bug

Before submitting a new issue please spend a couple of minutes on research:

* Check [🛑 Common issues](./DEBUG_TIPS.md#common-issues)
* Check [💡 Closed issues](https://github.com/jokob-sk/NetAlertX/issues?q=is%3Aissue+is%3Aclosed) if a similar issue was solved in the past.
* When submitting an issue ❗[enable debug](./DEBUG_TIPS.md)❗

⚠ Please follow the pre-defined issue template to resolve your issue faster.
