import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings

# ============================================================
#  ESP32 DISCOVERY STRATEGY (in priority order):
#  1. mDNS hostname  — http://esp32-fingerprint.local
#  2. Heartbeat file — IP saved by ESP32's boot POST call
#  3. Cached .esp32_ip file — last known working IP from scan
#  4. settings.ESP32_BASE_URL — hardcoded fallback default
#  5. Subnet scan   — brute-force scan of all 254 hosts
#
#  All timeouts are intentionally generous (1.5–2s) so that
#  temporary Wi-Fi jitter and ESP32 sensor-read delays do NOT
#  cause false "offline" reports.
# ============================================================

PROBE_TIMEOUT   = 1.5   # seconds — per-host ping during scan / quick check
CONNECT_TIMEOUT = 2.0   # seconds — TCP connect timeout for all requests
READ_TIMEOUT    = 4.0   # seconds — HTTP read timeout for all requests

_MDNS_HOSTNAME  = "esp32-fingerprint.local"
_MDNS_URL       = f"http://{_MDNS_HOSTNAME}"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def get_local_ip():
    """Return this machine's LAN IP (not 127.0.0.1)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Try a public IP (doesn't send traffic, just checks routing table)
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        try:
            # Fallback for disconnected networks with no default gateway
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            try:
                # Ultimate fallback
                IP = socket.gethostbyname(socket.gethostname())
                if IP.startswith('127.'):
                    # Try to get it via standard hostname
                    IP = socket.gethostbyname(socket.getfqdn())
            except Exception:
                IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def get_esp32_ip_file_path():
    return os.path.join(settings.BASE_DIR, '.esp32_ip')


def get_heartbeat_file_path():
    """Separate file written when ESP32 POSTs its own IP on boot."""
    return os.path.join(settings.BASE_DIR, '.esp32_heartbeat_ip')


def get_saved_esp32_url():
    """Read the last-scanned/cached URL from .esp32_ip."""
    ip_file = get_esp32_ip_file_path()
    if os.path.exists(ip_file):
        try:
            with open(ip_file, 'r') as f:
                url = f.read().strip()
                if url:
                    return url
        except Exception:
            pass
    return None


def get_heartbeat_url():
    """Read the URL that the ESP32 registered itself with on last boot."""
    hb_file = get_heartbeat_file_path()
    if os.path.exists(hb_file):
        try:
            with open(hb_file, 'r') as f:
                url = f.read().strip()
                if url:
                    return url
        except Exception:
            pass
    return None


def save_esp32_url(url):
    """Persist the working URL to .esp32_ip so next boot is instant."""
    ip_file = get_esp32_ip_file_path()
    try:
        with open(ip_file, 'w') as f:
            f.write(url)
    except Exception:
        pass


def save_heartbeat_url(url):
    """Called by the heartbeat view when ESP32 registers itself."""
    hb_file = get_heartbeat_file_path()
    try:
        with open(hb_file, 'w') as f:
            f.write(url)
        # Also update the main cache so every path benefits
        save_esp32_url(url)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------

def _is_esp32(url: str, timeout: float = PROBE_TIMEOUT) -> bool:
    """
    Return True if `url` hosts a valid ESP32 fingerprint module.
    Checks /status for the 'fingerprint_initialized' key.
    """
    try:
        resp = requests.get(
            f"{url}/status",
            timeout=(CONNECT_TIMEOUT, timeout),
            proxies={'http': None, 'https': None},
        )
        if resp.status_code == 200:
            data = resp.json()
            if "fingerprint_initialized" in data:
                return True
    except Exception:
        pass
    return False


def _test_ip_for_esp32(ip: str):
    """Used by the subnet scanner ThreadPoolExecutor."""
    url = f"http://{ip}"
    if _is_esp32(url, timeout=PROBE_TIMEOUT):
        return url
    return None


# ---------------------------------------------------------------------------
# Subnet scanner
# ---------------------------------------------------------------------------

def scan_subnet_for_esp32():
    """Scan all 254 hosts on the local /24 subnet in parallel."""
    local_ip = get_local_ip()
    if local_ip == '127.0.0.1':
        return None

    parts = local_ip.split('.')
    if len(parts) != 4:
        return None

    subnet = ".".join(parts[:3]) + "."
    ips = [f"{subnet}{i}" for i in range(1, 255)]

    print(f"[Biometric] Scanning {subnet}0/24 for ESP32 module...")
    with ThreadPoolExecutor(max_workers=60) as executor:
        results = executor.map(_test_ip_for_esp32, ips)
        for r in results:
            if r:
                return r
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_esp32_base_url(force_scan: bool = False) -> str:
    """
    Return the base URL of the ESP32 fingerprint module.
    Discovery order (skipped when force_scan=True):
      1. mDNS hostname (http://esp32-fingerprint.local)
      2. Heartbeat-registered IP (from ESP32's boot POST)
      3. Cached .esp32_ip file
      4. settings.ESP32_BASE_URL default
    Then falls through to active subnet scan.
    """
    default_url = getattr(settings, 'ESP32_BASE_URL', 'http://192.168.1.50').rstrip('/')

    if not force_scan:
        # ---- 1. Heartbeat-registered IP (ESP32 dynamically announced its IP on boot) ----
        hb_url = get_heartbeat_url()
        if hb_url and _is_esp32(hb_url):
            print(f"[Biometric] ESP32 found via heartbeat cache: {hb_url}")
            save_esp32_url(hb_url)
            return hb_url

        # ---- 2. Last cached IP from .esp32_ip (known working IP from previous scans) ----
        cached_url = get_saved_esp32_url()
        if cached_url and cached_url != hb_url and _is_esp32(cached_url):
            print(f"[Biometric] ESP32 found via IP cache: {cached_url}")
            return cached_url

        # ---- 3. mDNS hostname (works on routers supporting mDNS) ----
        try:
            resp = requests.get(
                f"{_MDNS_URL}/status",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                proxies={'http': None, 'https': None},
            )
            if resp.ok and "fingerprint_initialized" in resp.json():
                print(f"[Biometric] ESP32 found via mDNS: {_MDNS_URL}")
                save_esp32_url(_MDNS_URL)
                return _MDNS_URL
        except Exception:
            pass

        # ---- 4. Settings default URL ----
        if _is_esp32(default_url):
            print(f"[Biometric] ESP32 found at default URL: {default_url}")
            save_esp32_url(default_url)
            return default_url

    # ---- 5. Active subnet scan (last resort / force) ----
    print("[Biometric] Scanning local network for ESP32 module...")
    discovered = scan_subnet_for_esp32()
    if discovered:
        print(f"[Biometric] ESP32 auto-discovered at: {discovered}")
        save_esp32_url(discovered)
        return discovered

    # Nothing worked — return best guess so callers don't crash
    print(f"[Biometric] ESP32 not found anywhere. Falling back to: {default_url}")
    return default_url
