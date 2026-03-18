# NVX Preview Dashboard

A lightweight monitoring dashboard for Crestron DM-NVX AV-over-IP devices.  
See live previews of all your NVX devices on a single screen. Know which devices are online or offline at a glance.

---

## What It Does

- Live JPEG preview of every NVX device on one dashboard
- Online / Offline status updated every 10 seconds
- Filter devices by location — Floor, Zone, Room, Area
- Search by device name or IP address
- Click any device to expand full-size preview
- Works over WiFi — no wired connection required
- Configurable refresh interval — 5s, 10s, 15s, 30s

---

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.10 or later
- NVX devices must be on the same network as your PC

---

## Step 1 — Install Python

Download and install Python from the official website:

```
https://www.python.org/downloads/
```

> **Important:** During installation, tick **"Add Python to PATH"** at the bottom before clicking Install Now.

Verify installation:

```cmd
python --version
```

Expected output: `Python 3.x.x`

---

## Step 2 — Install Required Packages

Open **Command Prompt** and run these commands one by one:

**Upgrade pip first:**
```cmd
python -m pip install --upgrade pip
```

**Install FastAPI:**
```cmd
pip install fastapi
```

**Install Uvicorn:**
```cmd
pip install "uvicorn[standard]"
```

**Install Aiohttp:**
```cmd
pip install aiohttp
```

**Or install all at once:**
```cmd
pip install fastapi "uvicorn[standard]" aiohttp
```

**Verify all packages installed:**
```cmd
pip show fastapi uvicorn aiohttp
```

---

## Step 3 — Download the Project

Download or clone this repository into a folder on your PC.

```cmd
git clone https://github.com/yourusername/nvx-dashboard.git
cd nvx-dashboard
```

Or download the ZIP from GitHub and extract it.

Your folder should look like this:

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

Open `devices.json` in Notepad or any text editor and add your NVX device details:

```json
[
  {
    "id":           "nvx-01",
    "name":         "Boardroom",
    "ip":           "10.1.20.14",
    "location":     "Floor 1",
    "username":     "admin",
    "password":     "your_password",
    "preview_path": "/preview/preview_540px.jpeg",
    "use_https":    true
  },
  {
    "id":           "nvx-02",
    "name":         "Lobby",
    "ip":           "10.1.20.15",
    "location":     "Floor 1",
    "username":     "admin",
    "password":     "your_password",
    "preview_path": "/preview/preview_540px.jpeg",
    "use_https":    true
  }
]
```

**Field reference:**

| Field | Description |
|---|---|
| id | Unique ID for each device (nvx-01, nvx-02 ...) |
| name | Display name shown on the dashboard card |
| ip | IP address of the NVX device |
| location | Groups devices into filter tabs (Floor 1, Floor 2 etc.) |
| username | NVX web login username |
| password | NVX web login password |
| preview_path | Leave as `/preview/preview_540px.jpeg` for all NVX devices |
| use_https | Set to `true` if your NVX uses HTTPS (recommended) |

---

## Step 5 — Configure Settings (Optional)

Open `settings.json` to adjust performance settings:

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
| refresh_interval | Seconds between preview refreshes | 10 |
| fetch_timeout | Seconds before marking device offline | 8 |
| max_concurrent | How many devices to poll at the same time | 8 |
| preview_size | Preview image size: 135px / 270px / 540px | 540px |
| port | Web server port | 8000 |
| open_browser | Auto-open browser on start | true |

---

## Step 6 — Run the Dashboard

Open **Command Prompt** in your project folder and run:

```cmd
python app.py
```

The browser will open automatically at:

```
http://localhost:8000
```

To stop the server press **Ctrl + C** in the Command Prompt window.

---

## Reload Devices Without Restarting

If you edit `devices.json` while the server is running, reload without restarting:

```
http://localhost:8000/api/devices/reload
```

---

## Troubleshooting

### Browser Issues

**Browser shows nothing / page not found**
- Make sure you are opening `http://localhost:8000` and not `http://0.0.0.0:8000`
- Confirm the server is running — you should see `Uvicorn running on http://0.0.0.0:8000` in CMD
- Check `static/index.html` exists in your project folder

**ERR_CONNECTION_REFUSED**
- The server is not running — go to CMD and run `python app.py`
- Another app may be using port 8000 — change `port` in `settings.json` to `8001`

---

### Device Shows OFFLINE

**Step 1 — Check network connectivity**
```cmd
ping 10.1.20.14
```
If ping fails, your PC cannot reach the NVX device. Check network/WiFi.

**Step 2 — Test the preview URL in browser**
```
https://10.1.20.14/preview/preview_540px.jpeg
```
- If it shows the image → network is fine, check credentials
- If it asks for login → enter username and password manually to confirm they work
- If it shows nothing → NVX preview output may be disabled in device settings

**Step 3 — Check use_https setting**

If your NVX redirects HTTP to HTTPS, set `use_https` to `true` in `devices.json`:
```json
"use_https": true
```

**Step 4 — Try hostname instead of IP**
```cmd
ping DM-NVX-384-C4426888C775
```
If ping resolves, use the hostname in `devices.json` instead of the IP address.

---

### Authentication Errors (HTTP 401)

**Device shows AUTH FAILED on dashboard**

The username or password in `devices.json` is wrong.

> The app will automatically stop polling after 3 failed attempts to prevent account lockout on the NVX device.

**Fix:**

1. Correct the credentials in `devices.json`
2. Reload devices without restarting the server:
```
http://localhost:8000/api/devices/reload
```

Or unblock a specific device:
```
http://localhost:8000/api/devices/nvx-01/unblock
```

**Check current auth status for all devices:**
```
http://localhost:8000/api/status
```
Look for `"auth_blocked": true` — those devices have been stopped due to wrong credentials.

---

### Installation Issues

**pip is not recognized**

Python was not added to PATH. Reinstall Python and tick **"Add Python to PATH"** during setup.
```cmd
python -m pip install fastapi "uvicorn[standard]" aiohttp
```

**ModuleNotFoundError: No module named fastapi**

Packages not installed. Run:
```cmd
pip install fastapi "uvicorn[standard]" aiohttp
```

**SyntaxError on startup**

You may have an old version of `app.py`. Download the latest from GitHub and replace it.

**Port already in use**

Change the `port` value in `settings.json`:
```json
"port": 8001
```
Then open `http://localhost:8001`

**JSON syntax error in devices.json**

Validate your JSON at: `https://jsonlint.com`  
Common mistakes: trailing comma after last item, missing quotes around values.

---

### Performance Issues

**Preview images are slow to load**

- Increase `max_concurrent` in `settings.json` to poll more devices at once
- Reduce `preview_size` to `270px` for faster fetches over slow WiFi
- Check if your WiFi AP has client isolation enabled — disable it

**Dashboard is laggy with many devices**

- Increase `refresh_interval` to `15` or `30` seconds
- Reduce `max_concurrent` to `4` if the network is congested

---

## Building a Standalone Windows EXE

To package the dashboard as a `.exe` that runs on any Windows machine without Python:

**Install PyInstaller:**
```cmd
pip install pyinstaller
```

**Build the exe:**
```cmd
python build_exe.py
```

Output will be in:
```
dist\NVX_Dashboard\NVX_Dashboard.exe
```

Copy your `devices.json` and `settings.json` next to the exe before sharing.

---

## API Endpoints

| Endpoint | Description |
|---|---|
| GET / | Dashboard UI |
| GET /api/devices | List of all configured devices |
| GET /api/snapshot/{id} | Latest JPEG preview for a device |
| GET /api/status | Online/offline status of all devices — includes `auth_blocked` and `auth_fails` |
| GET /api/health | Server health and configuration info |
| GET /api/settings | Current settings loaded from settings.json |
| POST /api/devices/reload | Hot-reload devices.json without restart |
| POST /api/devices/{id}/unblock | Unblock a device that was blocked due to wrong credentials |

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| HTTP Client | aiohttp (async) |
| Frontend | Single HTML file, vanilla JavaScript |
| Protocol | HTTPS preview JPEG from NVX built-in endpoint |
| Packaging | PyInstaller (Windows exe) |

---

## Credits

Built and maintained by **Lucky Parihar**

- GitHub: [github.com/Luckyparihar11](https://github.com/Luckyparihar11)
- LinkedIn: [linkedin.com/in/lucky-parihar-b90425208](https://www.linkedin.com/in/lucky-parihar-b90425208/)

This project was born out of real frustration on large Crestron NVX deployments.
Built from scratch to solve a problem that every AV Engineer faces on site.

---

## License

MIT License — Copyright (c) 2026 Lucky Parihar

Free to use, modify, and distribute with attribution.  
See the [LICENSE](LICENSE) file for full terms.

---

## Feedback and Contributions

This is an initial release built from real project experience on large Crestron NVX deployments.

If you find a bug, have a feature request, or want to contribute — open an issue or pull request on GitHub.

---

> Designed and developed by Lucky Parihar  
> If this saved you time on a project — give it a star on GitHub!