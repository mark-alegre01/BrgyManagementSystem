import os
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a dummy address (doesn't send any traffic) to get the local interface IP
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _test_ip_for_esp32(ip):
    url = f"http://{ip}"
    try:
        # Query ESP32 status endpoint with a very short timeout
        resp = requests.get(f"{url}/status", timeout=0.3, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            if "fingerprint_initialized" in data:
                return url
    except Exception:
        pass
    return None

def scan_subnet_for_esp32():
    local_ip = get_local_ip()
    if local_ip == '127.0.0.1':
        return None
    
    parts = local_ip.split('.')
    if len(parts) != 4:
        return None
    
    subnet = ".".join(parts[:3]) + "."
    # Scan all 254 possible host addresses on the subnet in parallel
    ips = [f"{subnet}{i}" for i in range(1, 255)]
    
    with ThreadPoolExecutor(max_workers=60) as executor:
        results = executor.map(_test_ip_for_esp32, ips)
        for r in results:
            if r:
                return r
    return None

def get_esp32_ip_file_path():
    return os.path.join(settings.BASE_DIR, '.esp32_ip')

def get_saved_esp32_url():
    ip_file = get_esp32_ip_file_path()
    if os.path.exists(ip_file):
        try:
            with open(ip_file, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def save_esp32_url(url):
    ip_file = get_esp32_ip_file_path()
    try:
        with open(ip_file, 'w') as f:
            f.write(url)
    except Exception:
        pass

def get_esp32_base_url(force_scan=False):
    # 1. Try to read from saved file first (cached IP)
    saved_url = get_saved_esp32_url()
    if saved_url and not force_scan:
        return saved_url
    
    # 2. Try default settings URL if not forcing scan
    default_url = getattr(settings, 'ESP32_BASE_URL', 'http://192.168.1.50').rstrip('/')
    if not force_scan:
        try:
            resp = requests.get(f"{default_url}/status", timeout=0.5, proxies={'http': None, 'https': None})
            if resp.ok:
                save_esp32_url(default_url)
                return default_url
        except Exception:
            pass
            
    # 3. Trigger active subnet scan
    print("[Biometric] Scanning local network to locate ESP32 module...")
    discovered = scan_subnet_for_esp32()
    if discovered:
        print(f"[Biometric] ESP32 auto-discovered at: {discovered}")
        save_esp32_url(discovered)
        return discovered
        
    return default_url
