import ctypes
import os
import sys

def test_sdk():
    lib_path = "/home/mharkd/.gemini/antigravity/scratch/BrgyManagementSystem/core/libzkfp.so"
    print(f"Testing library at: {lib_path}")
    
    if not os.path.exists(lib_path):
        print("Error: Library file does not exist.")
        return

    try:
        from zk_sdk import ZKFingerSDK
        sdk = ZKFingerSDK()
        
        res = sdk.init_engine()
        if res == 0:
            print("Successfully initialized Fingerprint Engine!")
            sdk.terminate_engine()
        else:
            print(f"Failed to initialize Engine. Error code: {res}")
            print("Note: This might be due to missing sudo/udev rules or library conflicts.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_sdk()
