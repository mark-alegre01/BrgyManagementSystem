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

class ZKTecoEvents:
    def __init__(self):
        self.zk = None
        self.resident_id = None
        self.official_id = None
        self.profile_id = None
        self.base_url = None
        self.finished = False

    def OnFingerTouching(self):
        print("\n[Scanner] Finger detected on sensor...")

    def OnFingerLeaving(self):
        print("[Scanner] Finger removed.")

    def OnImageReceived(self, AImageValid):
        if AImageValid:
            print("[Scanner] Image captured successfully.")

    def OnFeatureInfo(self, AQuality):
        if AQuality < 80:
            print(f"[Scanner] Poor quality: {AQuality}. Please try again.")
        else:
            print(f"[Scanner] Good quality: {AQuality}")

    def OnEnroll(self, ActionResult, ATemplate):
        print(f"\n[Scanner] OnEnroll Triggered. ActionResult: {ActionResult}")
        if ActionResult:
            print("[SUCCESS] Enrollment completed!")
            self.send_template(ATemplate)
            self.finished = True
        else:
            print("[ERROR] Enrollment failed. Please try again.")

    def send_template(self, template):
        endpoint = ""
        if self.resident_id:
            endpoint = f"{self.base_url}/residents/{self.resident_id}/update-fingerprint/"
        elif self.official_id:
            endpoint = f"{self.base_url}/officials/{self.official_id}/update-fingerprint/"
        elif hasattr(self, 'profile_id') and self.profile_id:
            endpoint = f"{self.base_url}/officials/profile/{self.profile_id}/update-fingerprint/"
        
        if not endpoint:
            print("[Error] No target ID provided for template storage.")
            return

        print(f"[Network] Sending template to {endpoint}...")
        try:
            print(f"[Network] Template length: {len(template) if template else 0}")
        except Exception:
            pass
        try:
            # Send template as JSON
            response = requests.post(
                endpoint,
                json={"template": template},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                print("[Network] Template saved successfully in Django.")
            else:
                print(f"[Network] Failed to save template. Status: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"[Network] Error connecting to Django: {e}")

def main():
    parser = argparse.ArgumentParser(description="ZKTeco Biometric Service")
    parser.add_argument("--resident", help="Resident ID to enroll")
    parser.add_argument("--official", help="Official ID to enroll")
    parser.add_argument("--profile", help="UserProfile ID to enroll")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Django base URL")
    args = parser.parse_args()

    print("="*50)
    print(" ZKTeco ZK9500 Biometric Enrollment Service")
    print("="*50)

    try:
        # Create COM object then attach an event sink instance.
        # Using WithEvents ensures our state (profile_id/base_url) is stored on the real handler instance.
        zk_obj = win32com.client.Dispatch(PROGID)
        handler = WithEvents(zk_obj, ZKTecoEvents)
        handler.zk = zk_obj
        handler.resident_id = args.resident
        handler.official_id = args.official
        handler.profile_id = args.profile
        handler.base_url = args.url
        handler.finished = False

        print(f"[*] Target resident_id: {handler.resident_id}")
        print(f"[*] Target official_id: {handler.official_id}")
        print(f"[*] Target profile_id: {handler.profile_id}")
        print(f"[*] Django base_url: {handler.base_url}")
        
        print(f"[*] Connecting to {PROGID}...")
        result = zk_obj.InitEngine()
        if result != 0 and result != 2:
             print(f"[!] InitEngine returned {result}. Check if device is connected.")
        
        if not zk_obj.EngineValid:
            print("[!] Fingerprint engine is not valid. Is the device plugged in?")
            return

        print(f"[*] Engine Version: {zk_obj.FPEngineVersion}")
        print(f"[*] Sensor Count: {zk_obj.SensorCount}")

        # Some SDK versions require EnrollCount to be set explicitly.
        try:
            zk_obj.EnrollCount = 3
            print(f"[*] EnrollCount set to: {zk_obj.EnrollCount}")
        except Exception:
            pass
        
        print("\n[Action] Starting Enrollment Mode...")
        try:
            zk_obj.CancelEnroll()
        except Exception:
            pass
        zk_obj.BeginEnroll()
        print("[Status] Please press your finger on the sensor 3 times.")

        while not handler.finished:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)
        
    except Exception as e:
        print(f"[Fatal Error] {e}")
    finally:
        print("\n[*] Shutting down...")
        try:
            zk_obj.CancelEnroll()
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
