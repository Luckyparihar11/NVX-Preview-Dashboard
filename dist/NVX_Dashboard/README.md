# NVX Preview Dashboard  v2.0  —  Windows

## Folder structure

```
nvx-dashboard\
  app.py                  ← Server (don't edit)
  devices.json            ← YOUR DEVICES — edit this!
  settings.json           ← Optional tuning (port, refresh rate etc)
  START_DASHBOARD.bat     ← Double-click to run
  install_ffmpeg.ps1      ← One-click FFmpeg installer
  build_exe.py            ← Builds a .exe for distribution
  requirements.txt        ← Python packages
  static\
    index.html            ← Dashboard UI
  ffmpeg\
    ffmpeg.exe            ← Place ffmpeg.exe here (or install to PATH)
```

---

## Quick start

1. Right-click `install_ffmpeg.ps1` → Run with PowerShell
2. Edit `devices.json` with your real NVX device IPs
3. Double-click `START_DASHBOARD.bat`
4. Browser opens automatically at http://localhost:8000

---

## Editing devices.json

Open `devices.json` in Notepad or VS Code. Each device is one block:

```json
[
  {
    "id":        "nvx-01",
    "name":      "Boardroom",
    "ip":        "192.168.1.101",
    "location":  "Floor 1",
    "rtsp_port": 554,
    "rtsp_path": "/stream",
    "username":  null,
    "password":  null
  },
  {
    "id":        "nvx-02",
    "name":      "Lobby",
    "ip":        "192.168.1.102",
    "location":  "Floor 1",
    "rtsp_port": 554,
    "rtsp_path": "/stream",
    "username":  null,
    "password":  null
  }
]
```

Rules:
- Each device needs at minimum: id, name, ip
- location groups devices into filter tabs in the UI
- username / password: use null if no auth, or "admin" / "yourpass"
- rtsp_path: try /stream first, then /stream1, then /live/ch00_0

Reload devices without restarting: the dashboard has a
RELOAD button that calls /api/devices/reload automatically.

---

## settings.json

```json
{
  "snapshot_interval": 10,    ← seconds between refreshes
  "ffmpeg_timeout":    8,     ← seconds before marking device offline
  "max_concurrent":    8,     ← parallel FFmpeg processes
  "jpeg_quality":      3,     ← 2=best quality, 5=smaller file
  "rtsp_transport":   "tcp",  ← tcp=reliable, udp=lower latency
  "port":              8000,  ← web server port
  "open_browser":      true   ← auto-open browser on start
}
```

---

## Building a .exe

To create a standalone exe that works on any Windows machine
(no Python needed on the target machine):

```cmd
pip install pyinstaller
python build_exe.py
```

Output: dist\NVX_Dashboard\NVX_Dashboard.exe

To distribute:
1. Copy ffmpeg.exe into dist\NVX_Dashboard\ffmpeg\ffmpeg.exe
2. Edit dist\NVX_Dashboard\devices.json with real IPs
3. Zip the entire dist\NVX_Dashboard\ folder
4. Send the zip — recipient just unzips and double-clicks

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Browser shows nothing | Use http://localhost:8000 not http://0.0.0.0:8000 |
| All devices OFFLINE | Run install_ffmpeg.ps1, verify with: ffmpeg -version |
| Some devices OFFLINE | Ping device: ping 192.168.1.101 in CMD |
| Wrong image / black | Test RTSP in VLC: rtsp://192.168.1.101/stream |
| Port already in use | Change "port" in settings.json to 8001 |
| JSON syntax error | Validate at: https://jsonlint.com |
| .ps1 blocked by Windows | Run in PowerShell: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser |
