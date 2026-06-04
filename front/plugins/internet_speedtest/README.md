## Overview

A plugin allowing for executing regular internet speed tests.

### Usage

This plugin supports two engines:
1.  **Baseline Engine**: Uses the Python `speedtest-cli` library (default).
2.  **Native Engine (Optimized)**: Uses the official native Ookla Speedtest binary.

#### Native Speedtest Path
The plugin looks for the Speedtest binary at `/usr/bin/speedtest` by default. If the binary is located elsewhere, you can configure the path using the `NATIVE_SPEEDTEST_PATH` environment variable:

Example:
```env
NATIVE_SPEEDTEST_PATH=/custom/path/to/speedtest
```

If this variable is left unset, the plugin assumes `/usr/bin/speedtest`.

#### Opt-in for Native Engine
To use the native engine, you must provide the official binary to the container. The native binary is **strongly recommended** for internet connections > 100 Mbps to ensure CPU bottlenecks don't affect your results.

**Setup Instructions:**
1. **Download:** Get the official binary for your architecture from the [Speedtest CLI Homepage](https://www.speedtest.net/apps/cli).
2. **Place & Prepare:** Place the binary on your host machine (e.g., in `/opt/netalertx/`) and ensure it has executable permissions:

```bash
   chmod +x /opt/netalertx/speedtest
```

3. Docker Mapping: Map the host file to exactly `/usr/bin/speedtest` inside the container via your `docker-compose.yml`:

```yaml
services:
  netalertx:
    volumes:
      - /opt/netalertx/speedtest:/usr/bin/speedtest:ro
```

### Why this mapping?
Inside the container, a Python version of speedtest often exists in the virtual environment (`/opt/venv/bin/speedtest`). Mapping your native binary specifically to `/usr/bin/speedtest` allows the plugin to prioritize the high-performance native engine over the baseline library.

### Data Mapping

- **watchedValue1** — Download Speed (Mbps).
- **watchedValue2** — Upload Speed (Mbps).
- **watchedValue3** — Full JSON payload (useful for n8n or detailed webhooks).

### Notes

- The native binary is recommended for connections > 100 Mbps.
- If the native binary is not detected at /usr/bin/speedtest, or if it fails to execute, the plugin will seamlessly fall back to the baseline Python library.