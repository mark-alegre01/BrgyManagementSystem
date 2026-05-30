import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings

# ============================================================
#  ESP32 DISCOVERY STRATEGY (in priority order):
#
#  DEPLOYMENT MODE: Orange Pi runs as a WiFi hotspot (10.42.0.1)
#  The ESP32 ALWAYS connects to "Barangay_System_WiFi" and gets
#  a DHCP address in the 10.42.0.10 – 10.42.0.100 range.
#
#  Priority 1: Heartbeat file    — IP saved by ESP32's boot POST
#  Priority 2: Cached .esp32_ip  — last known working IP
#  Priority 3: mDNS hostname     — http://esp32-fingerprint.local
#  Priority 4: Hotspot scan      — brute-force scan of 10.42.0.10–100
#  Priority 5: settings fallback — ESP32_BASE_URL (last resort)
#
#  Timeouts are tight since the ESP32 is on the local hotspot —
#  no internet routing delay, sub-millisecond LAN latency.
# ============================================================

PROBE_TIMEOUT   = 0.8   # seconds — fast on local hotspot LAN
CONNECT_TIMEOUT = 1.0   # seconds — TCP connect on local LAN
READ_TIMEOUT    = 3.0   # seconds — HTTP read (sensor may be busy)

_MDNS_HOSTNAME  = "esp32-fingerprint.local"
_MDNS_URL       = f"http://{_MDNS_HOSTNAME}"

# The Orange Pi's private hotspot subnet (fixed — never changes)
_HOTSPOT_SUBNET = "10.42.0."
_HOTSPOT_DHCP_START = 10
_HOTSPOT_DHCP_END   = 100


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def get_local_ip():
    """Return this machine's LAN IP (not 127.0.0.1).
    On the Orange Pi, this will be 10.42.0.1 when routing to the hotspot subnet.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Try routing to the ESP32's subnet — will pick the wlan0 (hotspot) interface
        s.connect(('10.42.0.10', 1))
        IP = s.getsockname()[0]
    except Exception:
        try:
            s.connect(('8.8.8.8', 1))
            IP = s.getsockname()[0]
        except Exception:
            try:
                IP = socket.gethostbyname(socket.gethostname())
                if IP.startswith('127.'):
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
    """Used by the hotspot subnet scanner ThreadPoolExecutor."""
    url = f"http://{ip}"
    if _is_esp32(url, timeout=PROBE_TIMEOUT):
        return url
    return None


# ---------------------------------------------------------------------------
# Hotspot subnet scanner (fast — scans only the dnsmasq DHCP range)
# ---------------------------------------------------------------------------

def scan_hotspot_subnet_for_esp32():
    """
    Scan only the hotspot DHCP range (10.42.0.10 – 10.42.0.100).
    Much faster than a full /24 scan since we know exactly where the ESP32 will be.
    Runs in parallel with 30 workers (91 hosts max — completes in < 2 seconds).
    """
    ips = [f"{_HOTSPOT_SUBNET}{i}" for i in range(_HOTSPOT_DHCP_START, _HOTSPOT_DHCP_END + 1)]
    print(f"[Biometric] Scanning hotspot subnet {_HOTSPOT_SUBNET}{_HOTSPOT_DHCP_START}"
          f"–{_HOTSPOT_DHCP_END} for ESP32...")
    with ThreadPoolExecutor(max_workers=30) as executor:
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
      1. Heartbeat-registered IP  — ESP32 POSTs its IP on every boot
      2. Cached .esp32_ip file    — last known working IP
      3. mDNS hostname            — http://esp32-fingerprint.local

    Then falls through to active hotspot subnet scan (fast, < 2 seconds).
    """
    default_url = getattr(settings, 'ESP32_BASE_URL', 'http://10.42.0.10').rstrip('/')

    if not force_scan:
        # ---- 1. Heartbeat-registered IP (highest priority — set on ESP32 boot) ----
        hb_url = get_heartbeat_url()
        if hb_url and _is_esp32(hb_url):
            print(f"[Biometric] ESP32 found via heartbeat cache: {hb_url}")
            save_esp32_url(hb_url)
            return hb_url

        # ---- 2. Last cached IP from .esp32_ip ----
        cached_url = get_saved_esp32_url()
        if cached_url and cached_url != hb_url and _is_esp32(cached_url):
            print(f"[Biometric] ESP32 found via IP cache: {cached_url}")
            return cached_url

        # ---- 3. mDNS hostname (works if avahi / mDNS is available) ----
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

    # ---- 4. Hotspot subnet scan (fast — only scans DHCP range 10.42.0.10–100) ----
    discovered = scan_hotspot_subnet_for_esp32()
    if discovered:
        print(f"[Biometric] ESP32 found via hotspot scan: {discovered}")
        save_esp32_url(discovered)
        return discovered

    # ---- 5. Settings default (last resort — avoids crash if nothing works) ----
    print(f"[Biometric] ESP32 not found. Falling back to default: {default_url}")
    return default_url
