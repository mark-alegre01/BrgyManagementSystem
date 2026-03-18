import sys
import time
import json
import argparse
import requests
import pythoncom
import win32com.client
from win32com.client import WithEvents

# The ProgID we discovered from the registry
PROGID = "ZKFPEngXControl.ZKFPEngX"

class ZKVerifyEvents:
    def __init__(self):
        self.zk = None
        self.base_url = None
        self.request_id = None
        self.finished = False
        self.verified_user_id = None
        self.templates_data = [] # List of {'id': id, 'template': template}

    def OnFingerTouching(self):
        print("\n[Scanner] Finger detected...")

    def OnFingerLeaving(self):
        print("[Scanner] Finger removed.")

    def OnCapture(self, ActionResult, ATemplate):
        if not ActionResult:
            print("[Scanner] Capture failed.")
            return

        print("[Scanner] Image captured. Verifying...")
        
        # Identification 1:N
        # The ZKFPEngX OCX usually has a Verify method for 1:1 
        # For 1:N, we iterate through our templates
        found = False
        for entry in self.templates_data:
            user_id = entry['id']
            template = entry['template']
            
            # Verifying 1:1
            if self.zk and self.zk.VerFingerFromStr(template, ATemplate, False, False):
                print(f"[SUCCESS] User Match Found! ID: {user_id}")
                self.verified_user_id = user_id
                self.send_verification(user_id)
                self.finished = True
                found = True
                break
        
        if not found:
            print("[ERROR] No match found. Please try again.")

    def send_verification(self, user_id):
        endpoint = f"{self.base_url}/biometric-verify-login/"
        print(f"[Network] Notifying Django of successful verification for User ID: {user_id}...")
        try:
            response = requests.post(
                endpoint,
                json={"user_id": user_id, "request_id": self.request_id},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                print("[Network] Verification accepted. You may now log in.")
            else:
                print(f"[Network] Failed to notify Django. Status: {response.status_code}")
        except Exception as e:
            print(f"[Network] Error connecting to Django: {e}")

def main():
    parser = argparse.ArgumentParser(description="ZKTeco Biometric Verification Service")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Django base URL")
    parser.add_argument("--request-id", dest="request_id", help="Biometric request id for browser-session correlation")
    parser.add_argument("--role", dest="role", default="", help="Filter templates by role (captain/secretary/treasurer)")
    args = parser.parse_args()

    print("="*50)
    print(" ZKTeco ZK9500 Biometric Verification Service")
    print("="*50)

    try:
        # 1. Fetch all templates from Django first
        role = (args.role or "").strip()
        if role:
            print(f"[*] Fetching registered fingerprint templates for role: {role}...")
        else:
            print("[*] Fetching all registered fingerprint templates...")

        templates_url = f"{args.url}/biometric-templates/"
        if role:
            templates_url = f"{templates_url}?role={role}"

        response = requests.get(templates_url, timeout=10)
        if response.status_code != 200:
            print(f"[!] Failed to fetch templates. Status: {response.status_code}")
            return
        
        templates = response.json().get('templates', [])
        if not templates:
            print("[!] No registered fingerprints found in database.")
            return
        print(f"[*] Loaded {len(templates)} templates.")

        # 2. Initialize COM and attach event handler
        zk_obj = win32com.client.Dispatch(PROGID)
        handler = WithEvents(zk_obj, ZKVerifyEvents)
        handler.zk = zk_obj
        handler.base_url = args.url
        handler.request_id = args.request_id
        handler.templates_data = templates
        handler.finished = False
        
        print(f"[*] Connecting to {PROGID}...")
        if zk_obj.InitEngine() != 0:
             print(f"[!] InitEngine failed. Check device.")
             return
        
        print(f"[*] Engine Version: {zk_obj.FPEngineVersion}")
        print(f"[*] Sensor Count: {zk_obj.SensorCount}")
        
        print("\n[Action] Waiting for finger to Log In / Log Out...")
        
        while not handler.finished:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)
        
    except Exception as e:
        print(f"[Fatal Error] {e}")
    finally:
        print("\n[*] Shutting down...")
        try:
            zk_obj.EndEngine()
        except:
            pass
        print("[Done] Service closed.")

        try:
            input("\nPress Enter to close this window...")
        except Exception:
            pass

if __name__ == "__main__":
    main()
