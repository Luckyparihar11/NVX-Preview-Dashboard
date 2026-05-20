# NVX Preview Dashboard - FastAPI Backend
# HTTP Edition - fetches preview JPEGs directly from NVX web interface
# No FFmpeg required, no RTSP - just simple HTTP image fetching
#
# HOW TO RUN:
#   python app.py
#   Open: http://localhost:8000
#
# HOW TO EDIT DEVICES:
#   Edit devices.json only - no need to touch this file

import asyncio
import sys
import io
import json
import time
import logging
import threading
import webbrowser
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

# Windows asyncio fix - MUST be before any asyncio call
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Windows UTF-8 console fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import aiohttp
import concurrent.futures
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("nvx")


# ══════════════════════════════════════════════════════════════════
#  PATH RESOLUTION
#  Works as: python app.py  OR  NVX_Dashboard.exe (PyInstaller)
# ══════════════════════════════════════════════════════════════════
BASE_DIR      = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
STATIC_DIR    = BASE_DIR / "static"
DEVICES_JSON  = BASE_DIR / "devices.json"
SETTINGS_JSON = BASE_DIR / "settings.json"

log.info("Base dir : %s", BASE_DIR)
log.info("Devices  : %s", DEVICES_JSON)


# ══════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════
# Allowed polling intervals in seconds — shown as options in UI and API
POLL_INTERVALS = [1, 2, 4, 6]

DEFAULT_SETTINGS = {
    "refresh_interval": 10,      # seconds between preview fetches (legacy default)
    "poll_interval":    4,       # active poll interval — must be one of POLL_INTERVALS
    "fetch_timeout":    8,       # seconds before marking device offline
    "max_concurrent":   8,       # parallel HTTP requests at once
    "preview_size":     "540px", # 135px / 270px / 540px
    "port":             8000,
    "open_browser":     True,
}

def load_settings() -> dict:
    if SETTINGS_JSON.exists():
        try:
            with open(SETTINGS_JSON, encoding="utf-8") as f:
                user = json.load(f)
            merged = {**DEFAULT_SETTINGS, **user}
            log.info("Settings loaded from %s", SETTINGS_JSON)
            return merged
        except Exception as exc:
            log.warning("settings.json error (%s) - using defaults", exc)
    else:
        # Write default settings file so user can edit it
        try:
            with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2)
            log.info("Default settings.json created")
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

SETTINGS = load_settings()


# ══════════════════════════════════════════════════════════════════
#  DEVICE LOADING  -  from devices.json
# ══════════════════════════════════════════════════════════════════
TEMPLATE_DEVICES = [
    {
        "id":           "nvx-01",
        "name":         "My NVX Device",
        "ip":           "10.1.20.14",
        "location":     "Main",
        "username":     "admin",
        "password":     "Admin@123",
        "preview_path": "/preview/preview_540px.jpeg",
    }
]

def load_devices() -> List[dict]:
    if not DEVICES_JSON.exists():
        log.error("devices.json NOT FOUND at %s", DEVICES_JSON)
        try:
            with open(DEVICES_JSON, "w", encoding="utf-8") as f:
                json.dump(TEMPLATE_DEVICES, f, indent=2)
            log.info("Template devices.json created - edit it with your real IPs")
        except Exception as exc:
            log.error("Could not write template: %s", exc)
        return []

    try:
        with open(DEVICES_JSON, encoding="utf-8") as f:
            raw = json.load(f)
        valid = []
        for i, d in enumerate(raw):
            if "ip" not in d:
                log.warning("Device #%d missing 'ip' - skipped", i + 1)
                continue
            d.setdefault("id",           "nvx-%02d" % (i + 1))
            d.setdefault("name",         "Device %d" % (i + 1))
            d.setdefault("location",     "")
            d.setdefault("username",     None)
            d.setdefault("password",     None)
            # Build preview URL from ip if not explicitly set
            size = SETTINGS.get("preview_size", "540px")
            d.setdefault(
                "preview_path",
                "/preview/preview_%s.jpeg" % size
            )
            valid.append(d)
        log.info("Loaded %d devices from devices.json", len(valid))
        return valid
    except json.JSONDecodeError as exc:
        log.error("devices.json invalid JSON: %s", exc)
        return []
    except Exception as exc:
        log.error("Failed to load devices.json: %s", exc)
        return []

DEVICES: List[dict] = load_devices()


# ══════════════════════════════════════════════════════════════════
#  IN-MEMORY CACHE
# ══════════════════════════════════════════════════════════════════
# Max 401 failures before we stop polling the device
AUTH_FAIL_LIMIT = 3

@dataclass
class DeviceState:
    jpeg:              Optional[bytes] = None
    online:            bool            = False
    last_seen:         Optional[float] = None
    fetch_ms:          Optional[int]   = None
    error:             Optional[str]   = None
    http_code:         Optional[int]   = None
    auth_fails:        int             = 0
    auth_blocked:      bool            = False
    # ── Firmware / DeviceInfo (/Device/DeviceInfo/) ──────────
    firmware_version:  Optional[str]   = None   # e.g. "1.4789.00085.001"
    firmware_model:    Optional[str]   = None   # e.g. "DM-NVX-384"
    firmware_serial:   Optional[str]   = None
    firmware_mac:      Optional[str]   = None
    firmware_fetched:  Optional[float] = None
    firmware_error:    Optional[str]   = None
    # ── Network / Ethernet (/Device/Ethernet/) ───────────────
    net_hostname:      Optional[str]   = None   # device hostname
    net_ip:            Optional[str]   = None   # active IP address
    net_subnet:        Optional[str]   = None
    net_gateway:       Optional[str]   = None
    net_dhcp:          Optional[bool]  = None
    net_fetched:       Optional[float] = None
    net_error:         Optional[str]   = None
    # ── Multicast (/Device/StreamTransmit/ or StreamReceive/) ─
    multicast_address: Optional[str]   = None   # e.g. "239.255.1.1"
    multicast_source:  Optional[str]   = None   # "TX" or "RX"
    multicast_status:  Optional[str]   = None   # e.g. "Stream Started"
    multicast_fetched: Optional[float] = None
    multicast_error:   Optional[str]   = None
    # ── Session cookie (NVX requires web login before REST API) ──
    session_cookie:    Optional[str]   = None   # auth cookie after login
    session_fetched:   Optional[float] = None   # when cookie was obtained
    session_error:     Optional[str]   = None

cache: Dict[str, DeviceState] = {}
semaphore: Optional[asyncio.Semaphore] = None

def rebuild_cache():
    global cache
    cache = {d["id"]: DeviceState() for d in DEVICES}

rebuild_cache()


# ══════════════════════════════════════════════════════════════════
#  SSH STARTUP COMMANDS
#  Runs once ever per device — tracked in ssh_done.json next to app.py
#  Commands: loginattempts 0  and  SETLogoffidletime 0
#  Purpose:
#    loginattempts 0    — disables account lockout (0 = unlimited attempts)
#    SETLogoffidletime 0 — disables idle session timeout (0 = never logs off)
#  Uses same credentials as web login from devices.json
#  Requires: pip install paramiko
# ══════════════════════════════════════════════════════════════════

SSH_DONE_FILE  = BASE_DIR / "ssh_done.json"
SSH_PORT       = 22
SSH_TIMEOUT    = 10   # seconds to connect
SSH_COMMANDS   = [
    "loginattempts 0",
    "SETLogoffidletime 0",
]

def load_ssh_done() -> set:
    """Load set of device IDs that have already had SSH commands run."""
    if SSH_DONE_FILE.exists():
        try:
            with open(SSH_DONE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("completed", []))
        except Exception:
            pass
    return set()

def save_ssh_done(done: set):
    """Persist the set of completed device IDs to disk."""
    try:
        with open(SSH_DONE_FILE, "w", encoding="utf-8") as f:
            json.dump({"completed": sorted(done)}, f, indent=2)
    except Exception as exc:
        log.error("Could not save ssh_done.json: %s", exc)

def run_ssh_commands_sync(device: dict) -> dict:
    """
    Blocking SSH function — runs in a thread pool so it does not
    block the asyncio event loop.
    Returns a result dict with success/error info.
    """
    dev_id   = device["id"]
    ip       = device["ip"]
    username = device.get("username", "admin")
    password = device.get("password", "")

    result = {
        "device_id": dev_id,
        "ip":        ip,
        "success":   False,
        "commands":  [],
        "error":     None,
    }

    try:
        import paramiko
    except ImportError:
        result["error"] = "paramiko not installed — run: pip install paramiko"
        return result

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        log.info("[SSH][%s] Connecting to %s:%d ...", dev_id, ip, SSH_PORT)
        client.connect(
            hostname=ip,
            port=SSH_PORT,
            username=username,
            password=password,
            timeout=SSH_TIMEOUT,
            look_for_keys=False,
            allow_agent=False,
        )
        log.info("[SSH][%s] Connected — running %d commands", dev_id, len(SSH_COMMANDS))

        for cmd in SSH_COMMANDS:
            try:
                stdin, stdout, stderr = client.exec_command(cmd, timeout=SSH_TIMEOUT)
                out = stdout.read().decode("utf-8", errors="replace").strip()
                err = stderr.read().decode("utf-8", errors="replace").strip()
                exit_code = stdout.channel.recv_exit_status()
                cmd_result = {
                    "command":   cmd,
                    "output":    out,
                    "error":     err,
                    "exit_code": exit_code,
                    "ok":        exit_code == 0 or out != "" or err == "",
                }
                result["commands"].append(cmd_result)
                if cmd_result["ok"]:
                    log.info("[SSH][%s] OK: %s  ->  %s", dev_id, cmd, out or "done")
                else:
                    log.warning("[SSH][%s] WARN: %s  err=%s exit=%d",
                                dev_id, cmd, err, exit_code)
            except Exception as cmd_exc:
                result["commands"].append({
                    "command": cmd, "output": "", "error": str(cmd_exc),
                    "exit_code": -1, "ok": False,
                })
                log.warning("[SSH][%s] Command failed: %s  error=%s", dev_id, cmd, cmd_exc)

        result["success"] = True

    except Exception as exc:
        result["error"] = str(exc)
        log.warning("[SSH][%s] Connection failed: %s", dev_id, exc)
    finally:
        client.close()

    return result

async def run_ssh_startup():
    """
    On startup: for each device not yet in ssh_done.json,
    run SSH commands in a thread pool (non-blocking).
    Marks device as done after success and saves to ssh_done.json.
    """
    done = load_ssh_done()
    pending = [d for d in DEVICES if d["id"] not in done]

    if not pending:
        log.info("[SSH] All devices already configured — skipping SSH startup")
        return

    log.info("[SSH] Running startup commands on %d device(s) not yet configured",
             len(pending))

    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=min(len(pending), 5),
        thread_name_prefix="nvx-ssh",
    )

    async def run_one(device: dict):
        result = await loop.run_in_executor(
            executor, run_ssh_commands_sync, device
        )
        if result["success"]:
            done.add(device["id"])
            save_ssh_done(done)
            log.info("[SSH][%s] Done — marked as configured", device["id"])
        else:
            log.warning("[SSH][%s] Failed — will retry on next startup. Error: %s",
                        device["id"], result["error"])
        return result

    # Run all pending devices concurrently (up to 5 at once)
    results = await asyncio.gather(*[run_one(d) for d in pending])

    success = sum(1 for r in results if r["success"])
    failed  = len(results) - success
    log.info("[SSH] Startup complete — %d succeeded, %d failed", success, failed)
    if failed > 0:
        log.info("[SSH] Failed devices will be retried on next app.py start")

    executor.shutdown(wait=False)

# ══════════════════════════════════════════════════════════════════
#  EXTENDED DEVICE INFO FETCH
#  Fetches 3 endpoints in parallel:
#    /Device/DeviceInfo/      → firmware, model, serial, MAC
#    /Device/Ethernet/        → hostname, IP, subnet, gateway, DHCP
#    /Device/StreamTransmit/  → multicast address (TX)
#    /Device/StreamReceive/   → multicast address (RX fallback)
#  Rate-limited to DEVICE_INFO_INTERVAL seconds between refreshes.
# ══════════════════════════════════════════════════════════════════
DEVICE_INFO_INTERVAL = 300  # 5 minutes

def _base_url(device: dict) -> str:
    scheme = "https" if device.get("use_https", False) else "http"
    return "%s://%s" % (scheme, device["ip"])

# Session cookie expires after 1 hour on most NVX firmware
SESSION_TTL = 3600

async def _login_session(device: dict, tout: float) -> Optional[str]:
    """
    Log in to NVX web interface and return the session cookie string.
    NVX requires a browser-style form login before accepting REST API calls.
    Tries two known login endpoints used across different NVX firmware versions.
    Returns cookie string on success, None on failure.
    """
    base = _base_url(device)
    u    = device.get("username", "")
    p    = device.get("password", "")

    # Login form payloads — NVX firmware uses one of these two paths
    login_attempts = [
        # Newer firmware — JSON body
        {
            "url":     base + "/userlogin.html",
            "data":    {"login": u, "passwd": p},
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        },
        # Alternative path some firmware versions use
        {
            "url":     base + "/Device/UserSession/",
            "data":    None,
            "json":    {"Device": {"UserSession": {"UserName": u, "Password": p}}},
            "headers": {},
        },
    ]

    # Use a fresh per-device connector so cookies don't cross-contaminate
    connector = aiohttp.TCPConnector(ssl=False)
    jar       = aiohttp.CookieJar(unsafe=True)

    async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as login_sess:
        for attempt in login_attempts:
            try:
                kwargs = {
                    "timeout": aiohttp.ClientTimeout(total=tout),
                    "ssl":     False,
                    "headers": attempt.get("headers", {}),
                    "allow_redirects": True,
                }
                if attempt.get("json"):
                    kwargs["json"] = attempt["json"]
                else:
                    kwargs["data"] = attempt["data"]

                async with login_sess.post(attempt["url"], **kwargs) as resp:
                    # Accept 200 or 302 redirect — both mean login was processed
                    if resp.status in (200, 302, 303):
                        # Extract all cookies as a single header string
                        cookies = login_sess.cookie_jar.filter_cookies(attempt["url"])
                        if cookies:
                            cookie_str = "; ".join(
                                "%s=%s" % (k, v.value) for k, v in cookies.items()
                            )
                            log.info("[%s] Session login OK via %s | cookies: %s",
                                     device["id"], attempt["url"],
                                     list(cookies.keys()))
                            return cookie_str
                        # No cookies but 200 — try Basic Auth fallback on REST endpoints
                        log.debug("[%s] Login returned %d but no cookies — will try Basic Auth",
                                  device["id"], resp.status)
            except Exception as exc:
                log.debug("[%s] Login attempt failed (%s): %s",
                          device["id"], attempt["url"], exc)

    return None

async def _get_json(device: dict, url: str, session_cookie: Optional[str],
                    tout: float) -> Optional[dict]:
    """
    GET JSON from a NVX REST endpoint.
    Tries session cookie first, then falls back to Basic Auth.
    """
    u    = device.get("username", "")
    p    = device.get("password", "")

    # Build headers — prefer session cookie, fall back to Basic Auth
    headers = {}
    auth    = None
    if session_cookie:
        headers["Cookie"] = session_cookie
    else:
        auth = aiohttp.BasicAuth(login=u, password=p, encoding="latin1")

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as sess:
        try:
            async with sess.get(
                url,
                headers=headers,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=tout),
                ssl=False,
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                elif resp.status == 401:
                    log.debug("[%s] GET %s → 401 (session expired?)", device["id"], url)
                    return None
                else:
                    log.debug("[%s] GET %s → %d", device["id"], url, resp.status)
                    return None
        except Exception as exc:
            log.debug("[%s] GET %s failed: %s", device["id"], url, exc)
            return None

async def _ensure_session(device: dict, s: "DeviceState", tout: float):
    """
    Ensure a valid session cookie exists for this device.
    Refreshes if expired or missing.
    """
    now = time.time()
    if s.session_cookie and s.session_fetched and (now - s.session_fetched) < SESSION_TTL:
        return  # Cookie still valid

    log.info("[%s] Obtaining session cookie via web login...", device["id"])
    cookie = await _login_session(device, tout)
    if cookie:
        s.session_cookie  = cookie
        s.session_fetched = now
        s.session_error   = None
    else:
        s.session_cookie  = None
        s.session_error   = "Login failed — check credentials"
        log.warning("[%s] Session login failed — REST API calls will use Basic Auth fallback",
                    device["id"])

async def fetch_device_extended(session: aiohttp.ClientSession, device: dict):
    """Fetch firmware, network, and multicast info for one device."""
    s = cache.get(device["id"])
    if s is None:
        return

    # Rate-limit: skip if all three were fetched recently
    now = time.time()
    fw_due  = not s.firmware_fetched  or (now - s.firmware_fetched)  >= DEVICE_INFO_INTERVAL
    net_due = not s.net_fetched       or (now - s.net_fetched)       >= DEVICE_INFO_INTERVAL
    mc_due  = not s.multicast_fetched or (now - s.multicast_fetched) >= DEVICE_INFO_INTERVAL
    if not (fw_due or net_due or mc_due):
        return

    base = _base_url(device)
    tout = SETTINGS["fetch_timeout"]

    # Ensure we have a valid session cookie before hitting REST endpoints
    await _ensure_session(device, s, tout)
    cookie = s.session_cookie

    # ── Fetch all endpoints concurrently using session cookie ─
    dev_data, eth_data, tx_data, rx_data = await asyncio.gather(
        _get_json(device, base + "/Device/DeviceInfo/",     cookie, tout) if fw_due  else asyncio.sleep(0),
        _get_json(device, base + "/Device/Ethernet/",       cookie, tout) if net_due else asyncio.sleep(0),
        _get_json(device, base + "/Device/StreamTransmit/", cookie, tout) if mc_due  else asyncio.sleep(0),
        _get_json(device, base + "/Device/StreamReceive/",  cookie, tout) if mc_due  else asyncio.sleep(0),
    )

    # ── DeviceInfo ───────────────────────────────────────────
    if fw_due:
        if dev_data:
            try:
                info = dev_data.get("Device", {}).get("DeviceInfo", {})
                s.firmware_version = info.get("DeviceVersion")
                s.firmware_model   = info.get("Model")
                s.firmware_serial  = info.get("SerialNumber")
                s.firmware_mac     = info.get("MacAddress")
                s.firmware_fetched = now
                s.firmware_error   = None
                log.info("[%s] FW: %s | Model: %s | S/N: %s",
                         device["id"], s.firmware_version or "?",
                         s.firmware_model or "?", s.firmware_serial or "?")
            except Exception as exc:
                s.firmware_error = "parse error: %s" % exc
        else:
            s.firmware_error = "fetch failed"

    # ── Ethernet / Network ───────────────────────────────────
    if net_due:
        if eth_data:
            try:
                eth = eth_data.get("Device", {}).get("Ethernet", {})
                s.net_hostname = eth.get("HostName")
                # Pull IP from first adapter
                adapters = eth.get("Adapters", [])
                if adapters:
                    ipv4 = adapters[0].get("IPv4", {})
                    addrs = ipv4.get("Addresses", [])
                    if addrs:
                        s.net_ip     = addrs[0].get("Address")
                        s.net_subnet = addrs[0].get("SubnetMask")
                    s.net_gateway = ipv4.get("DefaultGateway")
                    s.net_dhcp    = ipv4.get("IsDhcpEnabled")
                s.net_fetched = now
                s.net_error   = None
                log.info("[%s] Network: hostname=%s ip=%s dhcp=%s",
                         device["id"], s.net_hostname or "?",
                         s.net_ip or "?", s.net_dhcp)
            except Exception as exc:
                s.net_error = "parse error: %s" % exc
        else:
            s.net_error = "fetch failed"

    # ── Multicast (TX first, fall back to RX) ───────────────
    if mc_due:
        mc_addr   = None
        mc_src    = None
        mc_status = None
        try:
            if tx_data:
                streams = tx_data.get("Device", {}).get("StreamTransmit", {}).get("Streams", [])
                if streams and isinstance(streams, list) and streams[0].get("MulticastAddress"):
                    mc_addr   = streams[0]["MulticastAddress"]
                    mc_status = streams[0].get("Status")
                    mc_src    = "TX"
            if not mc_addr and rx_data:
                streams = rx_data.get("Device", {}).get("StreamReceive", {}).get("Streams", [])
                if streams and isinstance(streams, list) and streams[0].get("MulticastAddress"):
                    mc_addr   = streams[0]["MulticastAddress"]
                    mc_status = streams[0].get("Status")
                    mc_src    = "RX"
        except Exception as exc:
            s.multicast_error = "parse error: %s" % exc
        s.multicast_address = mc_addr
        s.multicast_source  = mc_src
        s.multicast_status  = mc_status
        s.multicast_fetched = now
        s.multicast_error   = None if mc_addr else "not available"
        if mc_addr:
            log.info("[%s] Multicast: %s (%s) status=%s",
                     device["id"], mc_addr, mc_src or "?", mc_status or "?")

# Keep old name as alias for backward compat
fetch_firmware_info = fetch_device_extended

# ══════════════════════════════════════════════════════════════════
#  HTTP PREVIEW FETCH
# ══════════════════════════════════════════════════════════════════
def build_preview_url(device: dict) -> str:
    # Use https if device has use_https=true, otherwise try http
    scheme = "https" if device.get("use_https", False) else "http"
    return "%s://%s%s" % (scheme, device["ip"], device.get("preview_path", "/preview/preview_540px.jpeg"))

async def fetch_preview(session: aiohttp.ClientSession, device: dict) -> Optional[bytes]:
    # If credentials were already rejected - stop polling until user fixes devices.json
    s = cache.get(device["id"])
    if s and s.auth_blocked:
        log.debug("[%s] Skipping poll - auth blocked (wrong credentials)", device["id"])
        return None

    url  = build_preview_url(device)
    u    = device.get("username")
    p    = device.get("password")
    auth = aiohttp.BasicAuth(login=u, password=p, encoding="latin1") if u and p else None

    # ssl=False skips certificate verification (NVX uses self-signed certs)
    ssl_ctx = False

    try:
        async with session.get(
            url,
            auth=auth,
            timeout=aiohttp.ClientTimeout(total=SETTINGS["fetch_timeout"]),
            ssl=ssl_ctx,
        ) as resp:
            cache[device["id"]].http_code = resp.status

            # Some NVX devices redirect http -> https, follow it
            if resp.status in (301, 302, 307, 308):
                redirect_url = resp.headers.get("Location", "")
                log.info("[%s] Redirect to %s - update use_https to true in devices.json", device["id"], redirect_url)
                cache[device["id"]].error = "Redirect to HTTPS - set use_https:true in devices.json"
                return None

            if resp.status == 200:
                # Successful fetch - reset any previous auth failure count
                cache[device["id"]].auth_fails   = 0
                cache[device["id"]].auth_blocked = False
                data = await resp.read()
                if len(data) > 0:
                    return data
                log.warning("[%s] Empty response from %s", device["id"], url)
                return None

            elif resp.status == 401:
                s = cache[device["id"]]
                s.auth_fails += 1
                s.http_code   = 401
                if s.auth_fails >= AUTH_FAIL_LIMIT:
                    s.auth_blocked = True
                    s.error = "AUTH FAILED - wrong username or password. Edit devices.json and call /api/devices/reload"
                    log.error(
                        "[%s] Blocked after %d x 401 - wrong credentials. "
                        "Fix devices.json and reload via /api/devices/reload",
                        device["id"], AUTH_FAIL_LIMIT
                    )
                else:
                    s.error = "HTTP 401 - auth attempt %d of %d" % (s.auth_fails, AUTH_FAIL_LIMIT)
                    log.warning("[%s] HTTP 401 (%d of %d) - check credentials in devices.json",
                                device["id"], s.auth_fails, AUTH_FAIL_LIMIT)
                return None

            else:
                log.warning("[%s] HTTP %d from %s", device["id"], resp.status, url)
                cache[device["id"]].error = "HTTP %d" % resp.status
                return None

    except asyncio.TimeoutError:
        log.warning("[%s] Timeout fetching %s", device["id"], url)
        cache[device["id"]].error = "Timeout"
        return None
    except aiohttp.ClientConnectorError as exc:
        log.warning("[%s] Cannot connect to %s - %s", device["id"], url, exc)
        cache[device["id"]].error = "Cannot connect"
        return None
    except aiohttp.ClientSSLError as exc:
        log.warning("[%s] SSL error %s - trying https", device["id"], exc)
        cache[device["id"]].error = "SSL error - set use_https:true in devices.json"
        return None
    except Exception as exc:
        log.error("[%s] Fetch error: %s", device["id"], exc)
        cache[device["id"]].error = str(exc)
        return None


# ══════════════════════════════════════════════════════════════════
#  BACKGROUND REFRESH WORKER
# ══════════════════════════════════════════════════════════════════
async def refresh_device(session: aiohttp.ClientSession, device: dict):
    async with semaphore:
        t0   = time.monotonic()
        jpeg = await fetch_preview(session, device)
        ms   = int((time.monotonic() - t0) * 1000)
        s    = cache.get(device["id"])
        if s is None:
            return
        if jpeg:
            s.jpeg      = jpeg
            s.online    = True
            s.last_seen = time.time()
            s.fetch_ms  = ms
            s.error     = None
        else:
            s.online   = False
            s.fetch_ms = ms

        # Fetch firmware info in background (non-blocking, rate-limited internally)
        asyncio.create_task(fetch_firmware_info(session, device))

def get_poll_interval() -> float:
    """
    Returns the active poll interval in seconds.
    Reads from SETTINGS["poll_interval"] and validates against POLL_INTERVALS.
    Falls back to the closest allowed value if out of range.
    """
    requested = float(SETTINGS.get("poll_interval", 4))
    if requested in POLL_INTERVALS:
        return requested
    # Find closest allowed interval
    closest = min(POLL_INTERVALS, key=lambda x: abs(x - requested))
    log.warning(
        "poll_interval %.1fs not in allowed values %s — using %.1fs",
        requested, POLL_INTERVALS, closest
    )
    return float(closest)

def set_poll_interval(seconds: float) -> float:
    """
    Set poll interval live — no restart needed.
    Validates against POLL_INTERVALS, returns the value actually set.
    """
    if seconds not in POLL_INTERVALS:
        seconds = min(POLL_INTERVALS, key=lambda x: abs(x - seconds))
    SETTINGS["poll_interval"] = seconds
    log.info("Poll interval changed to %.1fs", seconds)
    return seconds

async def background_worker():
    global semaphore
    semaphore = asyncio.Semaphore(SETTINGS["max_concurrent"])

    if not DEVICES:
        log.warning("No devices configured - edit devices.json and restart")
        return

    interval = get_poll_interval()
    log.info(
        "HTTP worker started - %d devices | poll=%ds | allowed=%s | concurrency=%d",
        len(DEVICES), interval, POLL_INTERVALS, SETTINGS["max_concurrent"],
    )

    # Shared aiohttp session for all devices (connection pooling)
    # ssl=False disables cert verification globally for self-signed NVX certs
    connector = aiohttp.TCPConnector(
        limit=SETTINGS["max_concurrent"] * 2,
        ssl=False,
        force_close=False,
        enable_cleanup_closed=True,
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        # First pass - stagger so we don't spike the network simultaneously
        interval = get_poll_interval()
        stagger  = min(0.3, interval / max(len(DEVICES), 1))
        for i, device in enumerate(DEVICES):
            asyncio.create_task(_delayed_start(session, device, i * stagger))

        # Wait for the first full wave to complete
        await asyncio.sleep(interval + 2)

        # Continuous refresh loop — reads interval fresh each cycle
        # so changes via /api/poll/set take effect immediately
        while True:
            interval = get_poll_interval()
            t0       = time.monotonic()

            await asyncio.gather(*[refresh_device(session, d) for d in DEVICES])

            elapsed   = time.monotonic() - t0
            sleep_for = max(0.1, interval - elapsed)
            online    = sum(1 for s in cache.values() if s.online)
            log.info(
                "Cycle done %.1fs | %d/%d online | poll=%ds | sleep %.1fs",
                elapsed, online, len(DEVICES), interval, sleep_for,
            )
            await asyncio.sleep(sleep_for)

async def _delayed_start(session: aiohttp.ClientSession, device: dict, delay: float):
    await asyncio.sleep(delay)
    await refresh_device(session, device)


# ══════════════════════════════════════════════════════════════════
#  FASTAPI APP
# ══════════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(application: FastAPI):
    # Run SSH startup commands on any devices not yet configured
    asyncio.create_task(run_ssh_startup())
    # Start main preview + device info polling worker
    asyncio.create_task(background_worker())
    yield

app = FastAPI(title="NVX Preview Dashboard", version="3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pages ──────────────────────────────────────────────────────────
@app.get("/")
async def serve_index():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return JSONResponse(
            {"error": "index.html not found at %s" % index},
            status_code=500,
        )
    return FileResponse(str(index))

# ── Device API ─────────────────────────────────────────────────────
@app.get("/api/devices")
async def api_devices():
    return [
        {
            "id":           d["id"],
            "name":         d["name"],
            "ip":           d["ip"],
            "location":     d.get("location", ""),
            "preview_url":  "http://%s%s" % (d["ip"], d.get("preview_path", "")),
        }
        for d in DEVICES
    ]

@app.post("/api/devices/reload")
async def api_reload_devices():
    global DEVICES
    DEVICES = load_devices()
    rebuild_cache()
    asyncio.create_task(background_worker())
    return {"success": True, "count": len(DEVICES)}

# ── Snapshot API ───────────────────────────────────────────────────
@app.get("/api/snapshot/{device_id}")
async def api_snapshot(device_id: str):
    s = cache.get(device_id)
    if s is None:
        raise HTTPException(404, "Device not found: %s" % device_id)
    if not s.jpeg:
        raise HTTPException(503, "No preview yet - device may be offline or still loading")
    return Response(
        content=s.jpeg,
        media_type="image/jpeg",
        headers={
            "Cache-Control":   "no-store, no-cache, must-revalidate",
            "Pragma":          "no-cache",
            "X-Fetch-Ms":      str(s.fetch_ms or 0),
            "X-Device-Online": "1" if s.online else "0",
        },
    )

# ── Status ─────────────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    return {
        dev_id: {
            "online":             s.online,
            "last_seen":          s.last_seen,
            "fetch_ms":           s.fetch_ms,
            "has_frame":          s.jpeg is not None,
            "http_code":          s.http_code,
            "error":              s.error,
            "auth_blocked":       s.auth_blocked,
            "auth_fails":         s.auth_fails,
            # firmware
            "firmware_version":   s.firmware_version,
            "firmware_model":     s.firmware_model,
            "firmware_serial":    s.firmware_serial,
            "firmware_mac":       s.firmware_mac,
            "firmware_fetched":   s.firmware_fetched,
            "firmware_error":     s.firmware_error,
            # network
            "net_hostname":       s.net_hostname,
            "net_ip":             s.net_ip,
            "net_subnet":         s.net_subnet,
            "net_gateway":        s.net_gateway,
            "net_dhcp":           s.net_dhcp,
            "net_error":          s.net_error,
            # multicast
            "multicast_address":  s.multicast_address,
            "multicast_source":   s.multicast_source,
            "multicast_status":   s.multicast_status,
            "multicast_error":    s.multicast_error,
        }
        for dev_id, s in cache.items()
    }

@app.get("/api/firmware")
async def api_firmware_all():
    """Returns full device info (firmware, network, multicast) for all devices."""
    result = {}
    for d in DEVICES:
        dev_id = d["id"]
        s = cache.get(dev_id)
        if not s:
            continue
        result[dev_id] = {
            "name":               d.get("name"),
            "ip":                 d.get("ip"),
            "location":           d.get("location"),
            "online":             s.online,
            # firmware
            "firmware_version":   s.firmware_version,
            "firmware_model":     s.firmware_model,
            "firmware_serial":    s.firmware_serial,
            "firmware_mac":       s.firmware_mac,
            "firmware_error":     s.firmware_error,
            # network
            "net_hostname":       s.net_hostname,
            "net_ip":             s.net_ip,
            "net_subnet":         s.net_subnet,
            "net_gateway":        s.net_gateway,
            "net_dhcp":           s.net_dhcp,
            "net_error":          s.net_error,
            # multicast
            "multicast_address":  s.multicast_address,
            "multicast_source":   s.multicast_source,
            "multicast_status":   s.multicast_status,
            "multicast_error":    s.multicast_error,
        }
    return result

@app.get("/api/firmware/{device_id}")
async def api_firmware_one(device_id: str):
    s = cache.get(device_id)
    if s is None:
        raise HTTPException(404, "Device not found: %s" % device_id)
    d = next((x for x in DEVICES if x["id"] == device_id), {})
    return {
        "device_id":          device_id,
        "name":               d.get("name"),
        "ip":                 d.get("ip"),
        "online":             s.online,
        "firmware_version":   s.firmware_version,
        "firmware_model":     s.firmware_model,
        "firmware_serial":    s.firmware_serial,
        "firmware_mac":       s.firmware_mac,
        "firmware_error":     s.firmware_error,
        "net_hostname":       s.net_hostname,
        "net_ip":             s.net_ip,
        "net_subnet":         s.net_subnet,
        "net_gateway":        s.net_gateway,
        "net_dhcp":           s.net_dhcp,
        "net_error":          s.net_error,
        "multicast_address":  s.multicast_address,
        "multicast_source":   s.multicast_source,
        "multicast_status":   s.multicast_status,
        "multicast_error":    s.multicast_error,
    }

@app.post("/api/firmware/{device_id}/refresh")
async def api_firmware_refresh(device_id: str):
    """Force immediate re-fetch of all device info for one device."""
    s = cache.get(device_id)
    if s is None:
        raise HTTPException(404, "Device not found: %s" % device_id)
    s.firmware_fetched  = None
    s.net_fetched       = None
    s.multicast_fetched = None
    device = next((d for d in DEVICES if d["id"] == device_id), None)
    if device is None:
        raise HTTPException(404, "Device config not found")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        await fetch_device_extended(session, device)
    return {
        "success":           True,
        "device_id":         device_id,
        "firmware_version":  s.firmware_version,
        "net_hostname":      s.net_hostname,
        "net_ip":            s.net_ip,
        "multicast_address": s.multicast_address,
    }

@app.post("/api/firmware/refresh-all")
async def api_firmware_refresh_all():
    """Force immediate re-fetch of all device info for ALL devices."""
    for s in cache.values():
        s.firmware_fetched  = None
        s.net_fetched       = None
        s.multicast_fetched = None
    asyncio.create_task(background_worker())
    return {"success": True, "count": len(DEVICES)}

# ── Poll Interval API ──────────────────────────────────────────────
@app.get("/api/poll")
async def api_poll_get():
    """Get current poll interval and all allowed options."""
    return {
        "current_interval": get_poll_interval(),
        "allowed_intervals": POLL_INTERVALS,
        "unit": "seconds",
    }

@app.post("/api/poll/set/{seconds}")
async def api_poll_set(seconds: float):
    """
    Change poll interval live — no restart needed.
    Allowed values: 1, 2, 4, 6 seconds.
    Example: POST /api/poll/set/2
    """
    if seconds not in POLL_INTERVALS:
        raise HTTPException(
            400,
            "Invalid interval %.1fs — allowed values: %s" % (seconds, POLL_INTERVALS)
        )
    actual = set_poll_interval(seconds)
    return {
        "success":          True,
        "poll_interval":    actual,
        "allowed_intervals": POLL_INTERVALS,
        "message":          "Poll interval set to %.1fs — takes effect next cycle" % actual,
    }

@app.get("/api/ssh/status")
async def api_ssh_status():
    """Returns which devices have had SSH commands applied and which are pending."""
    done = load_ssh_done()
    result = []
    for d in DEVICES:
        result.append({
            "device_id": d["id"],
            "name":      d.get("name"),
            "ip":        d.get("ip"),
            "ssh_done":  d["id"] in done,
        })
    return {
        "total":    len(DEVICES),
        "done":     sum(1 for r in result if r["ssh_done"]),
        "pending":  sum(1 for r in result if not r["ssh_done"]),
        "devices":  result,
    }

@app.post("/api/ssh/reset")
async def api_ssh_reset():
    """
    Clear ssh_done.json so ALL devices run SSH commands again on next startup.
    Use this if you added new devices or want to re-apply commands.
    """
    if SSH_DONE_FILE.exists():
        SSH_DONE_FILE.unlink()
    return {"success": True, "message": "SSH done file cleared — commands will re-run on next startup"}

@app.post("/api/ssh/reset/{device_id}")
async def api_ssh_reset_one(device_id: str):
    """Remove one device from ssh_done.json so it re-runs on next startup."""
    done = load_ssh_done()
    if device_id not in done:
        return {"success": False, "message": "Device not in done list"}
    done.discard(device_id)
    save_ssh_done(done)
    return {"success": True, "device_id": device_id, "message": "Will re-run SSH on next startup"}

@app.post("/api/ssh/run/{device_id}")
async def api_ssh_run_now(device_id: str):
    """Run SSH commands on one specific device right now (regardless of done status)."""
    device = next((d for d in DEVICES if d["id"] == device_id), None)
    if device is None:
        raise HTTPException(404, "Device not found: %s" % device_id)
    loop    = asyncio.get_event_loop()
    result  = await loop.run_in_executor(None, run_ssh_commands_sync, device)
    if result["success"]:
        done = load_ssh_done()
        done.add(device_id)
        save_ssh_done(done)
    return result

@app.get("/api/export/csv")
async def api_export_csv():
    """Export all device info as a CSV file — downloadable from browser."""
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Name", "Location", "Config IP", "Status",
        "Firmware Version", "Model", "Serial Number", "MAC Address",
        "Hostname", "Active IP", "Subnet Mask", "Gateway", "DHCP",
        "Multicast Address", "Multicast Source", "Multicast Status",
    ])
    for d in DEVICES:
        dev_id = d["id"]
        s = cache.get(dev_id)
        if not s:
            continue
        writer.writerow([
            dev_id,
            d.get("name", ""),
            d.get("location", ""),
            d.get("ip", ""),
            "ONLINE" if s.online else "OFFLINE",
            s.firmware_version  or "",
            s.firmware_model    or "",
            s.firmware_serial   or "",
            s.firmware_mac      or "",
            s.net_hostname      or "",
            s.net_ip            or "",
            s.net_subnet        or "",
            s.net_gateway       or "",
            "DHCP" if s.net_dhcp else "Static" if s.net_dhcp is False else "",
            s.multicast_address or "",
            s.multicast_source  or "",
            s.multicast_status  or "",
        ])
    csv_bytes = output.getvalue().encode("utf-8")
    from datetime import datetime
    filename = "nvx_devices_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )

@app.post("/api/devices/{device_id}/unblock")
async def api_unblock_device(device_id: str):
    """Manually unblock a device that was blocked due to auth failure."""
    s = cache.get(device_id)
    if s is None:
        raise HTTPException(404, "Device not found: %s" % device_id)
    s.auth_blocked = False
    s.auth_fails   = 0
    s.error        = None
    log.info("[%s] Manually unblocked - will retry polling", device_id)
    return {"success": True, "device_id": device_id}

@app.get("/api/health")
async def api_health():
    online = sum(1 for s in cache.values() if s.online)
    return {
        "total":             len(DEVICES),
        "online":            online,
        "offline":           len(DEVICES) - online,
        "poll_interval":     get_poll_interval(),
        "allowed_intervals": POLL_INTERVALS,
        "preview_size":      SETTINGS.get("preview_size", "540px"),
        "mode":              "HTTP preview (no FFmpeg)",
        "platform":          sys.platform,
    }

@app.get("/api/settings")
async def api_settings():
    return SETTINGS

# ── Static files ───────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    log.error("static/ folder not found at %s", STATIC_DIR)


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════
def _open_browser(port: int):
    time.sleep(1.5)
    webbrowser.open("http://localhost:%d" % port)

if __name__ == "__main__":
    port = SETTINGS.get("port", 8000)

    print("")
    print("=" * 58)
    print("  NVX Preview Dashboard  -  HTTP Edition  v3.0")
    print("  http://localhost:%d" % port)
    print("=" * 58)
    print("  Mode     : HTTP preview images (no FFmpeg needed)")
    print("  Devices  : %d loaded" % len(DEVICES))
    print("  Poll     : every %ds  (options: %s)" % (get_poll_interval(), POLL_INTERVALS))
    print("  Quality  : %s preview" % SETTINGS.get("preview_size", "540px"))
    print("  Workers  : %d concurrent" % SETTINGS["max_concurrent"])
    if not DEVICES:
        print("")
        print("  [!] No devices - edit devices.json then restart")
    print("  Press Ctrl+C to stop")
    print("=" * 58)
    print("")

    if SETTINGS.get("open_browser", True):
        threading.Thread(
            target=_open_browser,
            args=(port,),
            daemon=True,
        ).start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,
        loop="asyncio",
        log_level="info",
    )