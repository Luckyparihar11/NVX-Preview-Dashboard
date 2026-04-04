# NVX Preview Dashboard — v3.0

> Built by **Lucky Parihar** · [GitHub](https://github.com/Luckyparihar11) · [LinkedIn](https://www.linkedin.com/in/lucky-parihar-b90425208/)

A lightweight monitoring dashboard for Crestron DM-NVX AV-over-IP devices.
Monitor live previews, device status, firmware versions, network info, and multicast addresses — all from one screen.

---

## What's New in v3.0

### Firmware & Device Info Panel
- Fetches firmware version, model, serial number, and MAC address from every NVX automatically
- Displayed on each device card footer and in the expanded lightbox view
- Full firmware table view accessible via the **⚙ FIRMWARE** button in the top bar

### Network Information
- Fetches hostname, active IP address, subnet mask, default gateway, and DHCP status from each device
- Visible in the firmware table — useful for verifying network config without opening each device's web UI

### Multicast Address Monitoring
- Fetches multicast address, source type (TX encoder / RX decoder), and stream status from each device
- Auto-detects TX (StreamTransmit) first, falls back to RX (StreamReceive) if TX has no multicast configured

### CSV Export
- One-click export of the entire device table to a timestamped CSV file
- Includes all columns: firmware, model, serial, MAC, hostname, IP, subnet, gateway, DHCP, multicast

### Auth Protection
- Stops polling after 3 consecutive 401 failures to prevent NVX account lockout
- Dashboard shows AUTH ERR badge — fix credentials in devices.json and reload without restart

### UI Refresh
- Full blue colour theme — replaced amber/yellow accent throughout
- Cleaner card footer with model name and firmware version on every card
- Lightbox now shows hostname and multicast address alongside firmware info

---

## Full Feature List

| Feature | Details |
|---|---|
| Live preview | HTTPS JPEG fetched from NVX built-in preview endpoint |
| Auto-refresh | Every 10s — configurable to 5s, 15s, 30s |
| Online / Offline | Instant status per device, updates every 3s |
| Location filter | Group devices by Floor, Zone, Room, Area |
| Search | By device name or IP address |
| Lightbox | Click any card to expand full-size preview |
| WiFi support | No wired connection required |
| Firmware version | Fetched from `/Device/DeviceInfo/` |
| Model + Serial + MAC | Fetched from `/Device/DeviceInfo/` |
| Hostname | Fetched from `/Device/Ethernet/` |
| Active IP + Subnet + Gateway | Fetched from `/Device/Ethernet/` |
| DHCP status | Fetched from `/Device/Ethernet/` |
| Multicast address | Fetched from `/Device/StreamTransmit/` or `/Device/StreamReceive/` |
| Multicast source | TX (encoder) or RX (decoder) auto-detected |
| Multicast status | Stream Started / Stream Stopped |
| CSV export | Download full table as timestamped CSV |
| Auth block | Stops after 3 x 401 — prevents NVX account lockout |
| Hot reload | Edit devices.json and reload without restart |
| Hostname support | Use device hostname instead of IP in devices.json |
| Standalone exe | Runs on any Windows PC without Python installed |

---

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.10 or later
- NVX devices must be on the same network as your PC

---

## Step 1 — Install Python

Download from the official website:
```
https://www.python.org/downloads/
```

> **Important:** During installation, tick **"Add Python to PATH"** before clicking Install Now.

Verify:
```cmd
python --version
```

---

## Step 2 — Install Required Packages

```cmd
pip install fastapi "uvicorn[standard]" aiohttp
```

Verify:
```cmd
pip show fastapi uvicorn aiohttp
```

---

## Step 3 — Download the Project

```cmd
git clone https://github.com/Luckyparihar11/nvx-dashboard.git
cd nvx-dashboard
```

Or download the ZIP from GitHub and extract it.

Your folder should contain:
```
nvx-dashboard/
  app.py
  devices.json
  settings.json
  static/
    index.html
```

---

## Step 4 — Add Your NVX Devices

Open `devices.json` in Notepad and add your devices:

```json
[
  {
    "id":           "nvx-01",
    "name":         "Boardroom",
    "ip":           "10.1.20.14",
    "location":     "Floor 1",
    "username":     "admin",
    "password":     "Admin@123",
    "preview_path": "/preview/preview_540px.jpeg",
    "use_https":    true
  },
  {
    "id":           "nvx-02",
    "name":         "Lobby",
    "ip":           "10.1.20.15",
    "location":     "Floor 1",
    "username":     "admin",
    "password":     "Admin@123",
    "preview_path": "/preview/preview_540px.jpeg",
    "use_https":    true
  }
]
```

**You can also use a hostname instead of IP:**
```json
"ip": "DM-NVX-384-C4426888C775"
```

Test hostname resolution first:
```cmd
ping DM-NVX-384-C4426888C775
```

**Field reference:**

| Field | Description |
|---|---|
| id | Unique ID — nvx-01, nvx-02 etc. |
| name | Display name on dashboard card |
| ip | IP address or hostname |
| location | Groups devices into filter tabs |
| username | NVX web login username |
| password | NVX web login password |
| preview_path | Leave as `/preview/preview_540px.jpeg` |
| use_https | Set `true` — NVX uses HTTPS by default |

---

## Step 5 — Configure Settings (Optional)

Open `settings.json`:

```json
{
  "refresh_interval": 10,
  "fetch_timeout": 8,
  "max_concurrent": 8,
  "preview_size": "540px",
  "port": 8000,
  "open_browser": true
}
```

| Setting | Description | Default |
|---|---|---|
| refresh_interval | Seconds between preview fetches | 10 |
| fetch_timeout | Seconds before marking device offline | 8 |
| max_concurrent | Parallel device polls at once | 8 |
| preview_size | 135px / 270px / 540px | 540px |
| port | Web server port | 8000 |
| open_browser | Auto-open browser on start | true |

---

## Step 6 — Run the Dashboard

```cmd
python app.py
```

Browser opens automatically at:
```
http://localhost:8000
```

Press **Ctrl + C** to stop.

---

## Using the Firmware Table

Click the **⚙ FIRMWARE** button in the top bar to switch to the device information table.

The table shows for every device:

| Column | Source API |
|---|---|
| Status | Live poll |
| Firmware Version | `/Device/DeviceInfo/` |
| Model | `/Device/DeviceInfo/` |
| Serial Number | `/Device/DeviceInfo/` |
| MAC Address | `/Device/DeviceInfo/` |
| Hostname | `/Device/Ethernet/` |
| Active IP | `/Device/Ethernet/` |
| Subnet | `/Device/Ethernet/` |
| Gateway | `/Device/Ethernet/` |
| DHCP | `/Device/Ethernet/` |
| Multicast Address | `/Device/StreamTransmit/` or `/Device/StreamReceive/` |
| MC Source | TX or RX auto-detected |
| MC Status | Stream Started / Stopped |

Firmware info is fetched automatically on startup and refreshed every **5 minutes**.
It uses the same credentials as the preview — no extra config required.

---

## Exporting Data as CSV

Click **⬇ EXPORT CSV** in the firmware table header.

A file named `nvx_devices_YYYYMMDD_HHMMSS.csv` downloads instantly with all 17 columns.

Or call the endpoint directly:
```
http://localhost:8000/api/export/csv
```

---

## Reload Devices Without Restarting

Edit `devices.json` while the server is running, then:
```
http://localhost:8000/api/devices/reload
```

---

## Troubleshooting

### Browser Issues

**Browser shows nothing / page not found**
- Open `http://localhost:8000` — not `http://0.0.0.0:8000`
- Confirm server is running — CMD should show `Uvicorn running on http://0.0.0.0:8000`

**ERR_CONNECTION_REFUSED**
- Server is not running — run `python app.py`
- Port conflict — change `port` in settings.json to `8001`

---

### Device Shows OFFLINE

**Step 1 — Check network**
```cmd
ping 10.1.20.14
```

**Step 2 — Test preview URL in browser**
```
https://10.1.20.14/preview/preview_540px.jpeg
```

**Step 3 — Check use_https**
```json
"use_https": true
```

**Step 4 — Try hostname**
```cmd
ping DM-NVX-384-C4426888C775
```

---

### Authentication Errors (HTTP 401)

The app stops polling after **3 failed attempts** to prevent NVX account lockout.

**Fix:**
1. Correct credentials in `devices.json`
2. Reload:
```
http://localhost:8000/api/devices/reload
```

Unblock one device:
```
http://localhost:8000/api/devices/nvx-01/unblock
```

Check auth status:
```
http://localhost:8000/api/status
```
Look for `"auth_blocked": true`

---

### Firmware Table Shows "fetching..."

This is normal on first startup — firmware is fetched once per device and takes a few seconds.
If it stays on "fetching..." after 30 seconds:

- Device may be offline or unreachable
- `/Device/DeviceInfo/` endpoint may not be supported on older NVX firmware
- Check `firmware_error` in `/api/status` for the specific error

Force re-fetch all devices:
```
POST http://localhost:8000/api/firmware/refresh-all
```

Force re-fetch one device:
```
POST http://localhost:8000/api/firmware/nvx-01/refresh
```

---

### Installation Issues

**pip is not recognized**
```cmd
python -m pip install fastapi "uvicorn[standard]" aiohttp
```

**Port already in use**
Change `port` in settings.json:
```json
"port": 8001
```

**JSON syntax error in devices.json**
Validate at: `https://jsonlint.com`

---

### Performance Issues

**Slow previews over WiFi**
- Increase `fetch_timeout` to `15` in settings.json
- Reduce `max_concurrent` to `4`
- Reduce `preview_size` to `270px`

**Dashboard laggy with many devices**
- Increase `refresh_interval` to `15` or `30`

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard UI |
| `/api/devices` | GET | List of all configured devices |
| `/api/devices/reload` | POST | Hot-reload devices.json |
| `/api/devices/{id}/unblock` | POST | Unblock auth-blocked device |
| `/api/snapshot/{id}` | GET | Latest JPEG preview for a device |
| `/api/status` | GET | Full status for all devices including firmware + network + multicast |
| `/api/health` | GET | Server health and config info |
| `/api/settings` | GET | Current settings.json values |
| `/api/firmware` | GET | Firmware + network + multicast info for all devices |
| `/api/firmware/{id}` | GET | Full info for one device |
| `/api/firmware/{id}/refresh` | POST | Force re-fetch info for one device |
| `/api/firmware/refresh-all` | POST | Force re-fetch info for all devices |
| `/api/export/csv` | GET | Download full device table as CSV |

---

## Building a Standalone Windows EXE

```cmd
pip install pyinstaller
python build_exe.py
```

Output:
```
dist\NVX_Dashboard\NVX_Dashboard.exe
```

Copy your config files alongside:
```cmd
xcopy /E /I static dist\NVX_Dashboard\static
copy devices.json dist\NVX_Dashboard\devices.json
copy settings.json dist\NVX_Dashboard\settings.json
```

---

## Architecture

```
NVX Devices (HTTPS)
      ↓
  app.py (FastAPI + aiohttp)
      ├── /preview/preview_540px.jpeg  → JPEG cache → /api/snapshot
      ├── /Device/DeviceInfo/          → firmware cache
      ├── /Device/Ethernet/            → network cache
      └── /Device/StreamTransmit|Receive/ → multicast cache
                    ↓
            /api/status  (polled every 3s by browser)
                    ↓
            index.html  (dashboard UI)
```

---

## Changelog

### v3.0 (2026)
- Added firmware version, model, serial, MAC fetch from `/Device/DeviceInfo/`
- Added hostname, IP, subnet, gateway, DHCP fetch from `/Device/Ethernet/`
- Added multicast address fetch from `/Device/StreamTransmit/` and `/Device/StreamReceive/`
- Added firmware table view with 17 columns
- Added CSV export — `/api/export/csv`
- Added force refresh endpoints — `/api/firmware/refresh-all`
- Added auth block protection — stops after 3 x 401
- Added hostname support in devices.json
- Blue colour theme replacing amber/yellow
- Firmware version + model shown on every device card
- Lightbox now shows hostname and multicast address

### v2.0
- Switched from RTSP/FFmpeg to HTTP preview JPEG
- No FFmpeg required
- Added devices.json and settings.json config files
- Added hot-reload via `/api/devices/reload`
- Added Windows exe build via PyInstaller

### v1.0
- Initial release
- RTSP preview via FFmpeg
- Multi-device grid dashboard
- Location filter tabs
- Search by name or IP

---

## Credits

Built and maintained by **Lucky Parihar**

- GitHub: [github.com/Luckyparihar11](https://github.com/Luckyparihar11)
- LinkedIn: [linkedin.com/in/lucky-parihar-b90425208](https://www.linkedin.com/in/lucky-parihar-b90425208/)

Built from real project frustration on large Crestron NVX deployments.
If this saved you time — give it a star on GitHub.

---

## License

MIT License — Copyright (c) 2026 Lucky Parihar

See [LICENSE](LICENSE) for full terms.

> This project is not affiliated with or endorsed by Crestron Electronics, Inc.