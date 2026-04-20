import sys
import time
import json
import argparse
import requests
from zk_sdk import ZKFingerSDK, log_message

class ZKVerifyService:
    def __init__(self, base_url, request_id, templates_data):
        log_message(f"Initializing ZKVerifyService for request {request_id}")
        self.sdk = ZKFingerSDK()

        self.base_url = base_url
        self.request_id = request_id
        self.templates_data = templates_data
        self.finished = False

    def run(self):
        log_message("ZKVerifyService.run() started")
        if not self.sdk.init_engine():
            log_message("ZKVerifyService: Failed to initialize Fingerprint Engine.")
            print("[!] Failed to initialize Fingerprint Engine.")
            return

        if not self.sdk.open_device():
            log_message("ZKVerifyService: Failed to open Fingerprint Device.")
            print("[!] Failed to open Fingerprint Device.")
            return


        hDB = self.sdk.get_db_handle()
        if not hDB:
            print("[!] Failed to initialize Fingerprint Database.")
            return

        print("\n[Action] Waiting for finger to Log In / Log Out...")
        try:
            while not self.finished:
                # Polling for capture (abstracted for now as we'd need more SDK bindings)
                # In a real SDK wrapper, we'd call self.sdk.capture()
                # For now, we provide the structure for the user's Linux library.
                time.sleep(0.5)
                
                # Placeholder for actual verification logic once SDK methods are expanded
                # if self.sdk.is_finger_on_sensor():
                #    img = self.sdk.capture()
                #    ... verify ...
        except KeyboardInterrupt:
            pass
        finally:
            self.sdk.close_device()
            self.sdk.terminate_engine()

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
    print(" ZKTeco ZK9500 Biometric Verification Service (Cross-Platform)")
    print("="*50)

    try:
        # Fetch all templates from Django first
        role = (args.role or "").strip()
        templates_url = f"{args.url}/biometric-templates/"
        if role:
            templates_url = f"{templates_url}?role={role}"

        print(f"[*] Fetching templates from {templates_url}...")
        response = requests.get(templates_url, timeout=10)
        if response.status_code != 200:
            print(f"[!] Failed to fetch templates. Status: {response.status_code}")
            return
        
        templates = response.json().get('templates', [])
        if not templates:
            print("[!] No registered fingerprints found in database.")
            return
        print(f"[*] Loaded {len(templates)} templates.")

        service = ZKVerifyService(args.url, args.request_id, templates)
        service.run()
        
    except Exception as e:
        print(f"[Fatal Error] {e}")

if __name__ == "__main__":
    main()

