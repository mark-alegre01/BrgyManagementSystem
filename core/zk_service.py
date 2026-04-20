import sys
import time
import json
import argparse
import requests
from zk_sdk import ZKFingerSDK

class ZKTecoEnrollService:
    def __init__(self, base_url, resident_id=None, official_id=None, profile_id=None):
        self.sdk = ZKFingerSDK()
        self.base_url = base_url
        self.resident_id = resident_id
        self.official_id = official_id
        self.profile_id = profile_id
        self.finished = False

    def run(self):
        if not self.sdk.init_engine():
            print("[!] Failed to initialize Fingerprint Engine.")
            return

        if not self.sdk.open_device():
            print("[!] Failed to open Fingerprint Device.")
            return

        print(f"[*] Target resident_id: {self.resident_id}")
        print(f"[*] Target official_id: {self.official_id}")
        print(f"[*] Target profile_id: {self.profile_id}")
        print(f"[*] Django base_url: {self.base_url}")
        
        print("\n[Action] Starting Enrollment Mode...")
        print("[Status] Please press your finger on the sensor 3 times.")
        
        try:
            # Polling for enrollment (Skeleton for Linux SDK usage)
            while not self.finished:
                time.sleep(0.5)
                # Actual SDK capture and enrollment logic would go here
                # if enrollment_done:
                #    self.send_template(template)
                #    self.finished = True
        except KeyboardInterrupt:
            pass
        finally:
            self.sdk.close_device()
            self.sdk.terminate_engine()

    def send_template(self, template):
        endpoint = ""
        if self.resident_id:
            endpoint = f"{self.base_url}/residents/{self.resident_id}/update-fingerprint/"
        elif self.official_id:
            endpoint = f"{self.base_url}/officials/{self.official_id}/update-fingerprint/"
        elif self.profile_id:
            endpoint = f"{self.base_url}/officials/profile/{self.profile_id}/update-fingerprint/"
        
        if not endpoint:
            print("[Error] No target ID provided for template storage.")
            return

        print(f"[Network] Sending template to {endpoint}...")
        try:
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
        except Exception as e:
            print(f"[Network] Error connecting to Django: {e}")

def main():
    parser = argparse.ArgumentParser(description="ZKTeco Biometric Enrollment Service")
    parser.add_argument("--resident", help="Resident ID to enroll")
    parser.add_argument("--official", help="Official ID to enroll")
    parser.add_argument("--profile", help="UserProfile ID to enroll")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Django base URL")
    args = parser.parse_args()

    print("="*50)
    print(" ZKTeco ZK9500 Biometric Enrollment Service (Cross-Platform)")
    print("="*50)

    try:
        service = ZKTecoEnrollService(
            base_url=args.url,
            resident_id=args.resident,
            official_id=args.official,
            profile_id=args.profile
        )
        service.run()
    except Exception as e:
        print(f"[Fatal Error] {e}")

if __name__ == "__main__":
    main()

