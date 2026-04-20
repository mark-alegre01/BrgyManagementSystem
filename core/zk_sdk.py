import ctypes
import os
import sys
import base64

class ZKFingerSDK:
    def __init__(self):
        self.lib = None
        self.hManager = None
        self.hDevice = None
        self.hDB = None
        try:
            self._load_library()
        except Exception:
            pass

    def _load_library(self):
        if os.name == 'nt': # Windows
            dll_path = r"C:\Windows\System32\ZKFPCap.dll"
            if not os.path.exists(dll_path):
                dll_path = r"C:\Windows\SysWOW64\ZKFPCap.dll"
            
            if not os.path.exists(dll_path):
                 raise FileNotFoundError("ZKFPCap.dll not found in System32 or SysWOW64")

            self.lib = ctypes.WinDLL(dll_path)
            print(f"Loaded Windows SDK from {dll_path}")
        else: # Linux
            # Try to find libzkfp.so in common paths
            so_paths = [
                "/usr/lib/libzkfp.so",
                "/usr/local/lib/libzkfp.so",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "libzkfp.so")
            ]
            
            self.lib = None
            for p in so_paths:
                if os.path.exists(p):
                    try:
                        self.lib = ctypes.CDLL(p)
                        print(f"Loaded Linux SDK from {p}")
                        break
                    except Exception as e:
                        print(f"Failed to load {p}: {e}")
            
            if not self.lib:
                # Fallback to system search
                try:
                    self.lib = ctypes.CDLL("libzkfp.so")
                    print("Loaded Linux SDK from system path")
                except Exception:
                    raise FileNotFoundError("libzkfp.so not found. Please install ZKTeco Linux SDK.")

    def init_engine(self):
        if not self.lib: return False
        res = self.lib.ZKFP_Init()
        return res == 0

    def terminate_engine(self):
        if self.lib:
            self.lib.ZKFP_Terminate()

    def open_device(self, index=0):
        if not self.lib: return False
        self.lib.ZKFP_OpenDevice.restype = ctypes.c_void_p
        self.hDevice = self.lib.ZKFP_OpenDevice(index)
        return self.hDevice is not None

    def close_device(self):
        if self.hDevice and self.lib:
            self.lib.ZKFP_CloseDevice(self.hDevice)
            self.hDevice = None

    def get_db_handle(self):
        if not self.lib: return None
        self.lib.ZKFP_DBInit.restype = ctypes.c_void_p
        self.hDB = self.lib.ZKFP_DBInit()
        return self.hDB

    def free_db_handle(self):
        if self.hDB and self.lib:
            self.lib.ZKFP_DBFree(self.hDB)
            self.hDB = None


    # Add more methods as needed for capture/match
