import ctypes
import os
import sys
import base64

class ZKFingerSDK:
    def __init__(self):
        self.lib = None
        self._load_library()
        self.hManager = None
        self.hDevice = None
        self.hDB = None

    def _load_library(self):
        # The DLLs were found in C:\Windows\System32
        dll_path = r"C:\Windows\System32\ZKFPCap.dll"
        if not os.path.exists(dll_path):
            # Try SysWOW64 if System32 fails or if running 32-bit python
            dll_path = r"C:\Windows\SysWOW64\ZKFPCap.dll"
            
        try:
            self.lib = ctypes.WinDLL(dll_path)
            print(f"Loaded SDK from {dll_path}")
        except Exception as e:
            print(f"Failed to load ZKFP DLL: {e}")
            raise

    def init_engine(self):
        # int ZKFP_Init()
        res = self.lib.ZKFP_Init()
        if res == 0:
            return True
        return False

    def terminate_engine(self):
        if self.lib:
            self.lib.ZKFP_Terminate()

    def open_device(self, index=0):
        # HANDLE ZKFP_OpenDevice(int index)
        self.lib.ZKFP_OpenDevice.restype = ctypes.c_void_p
        self.hDevice = self.lib.ZKFP_OpenDevice(index)
        return self.hDevice is not None

    def close_device(self):
        if self.hDevice:
            self.lib.ZKFP_CloseDevice(self.hDevice)
            self.hDevice = None

    def get_db_handle(self):
        # HANDLE ZKFP_DBInit()
        self.lib.ZKFP_DBInit.restype = ctypes.c_void_p
        self.hDB = self.lib.ZKFP_DBInit()
        return self.hDB

    def free_db_handle(self):
        if self.hDB:
            self.lib.ZKFP_DBFree(self.hDB)
            self.hDB = None

    # Add more methods as needed for capture/match
