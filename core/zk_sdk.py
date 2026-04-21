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
        else: # Linux
            # Identify core directory
            core_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Re-order dependencies for strict sequential loading
            deps = [
                "libusb-0.1.so.4",
                "libcrypto.so.0.9.8",
                "libsqlite3.so.0",
                "libiomp5.so",
                "libidkit.so.2",
                "libsilkidcap.so",
                "libzkfinger10.so"
            ]
            
            # Pre-load dependencies with absolute paths and GLOBAL symbols
            # This allows the linker to find them when libzkfp.so is loaded
            for dep in deps:
                dep_path = os.path.join(core_dir, dep)
                if os.path.exists(dep_path):
                    try:
                        ctypes.CDLL(dep_path, mode=ctypes.RTLD_GLOBAL)
                    except Exception as e:
                        print(f"DEBUG: Could not pre-load {dep}: {e}")

            # Now try to load the main library
            so_paths = [
                os.path.join(core_dir, "libzkfp.so"),
                "/usr/local/lib/libzkfp.so",
                "/usr/lib/libzkfp.so"
            ]
            
            self.lib = None
            for p in so_paths:
                if os.path.exists(p):
                    try:
                        self.lib = ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
                        break
                    except Exception as e:
                        print(f"DEBUG: Failed to load {p}: {e}")
            
            if not self.lib:
                # Fallback to system search
                try:
                    self.lib = ctypes.CDLL("libzkfp.so", mode=ctypes.RTLD_GLOBAL)
                except Exception:
                    raise FileNotFoundError("libzkfp.so not found. Please ensure all .so files are in the core/ folder.")

    def _get_func(self, name):
        """Helper to get function from either ZKFP_ or ZKFPM_ prefix."""
        if not self.lib: return None
        
        # Try original name
        if hasattr(self.lib, name):
            return getattr(self.lib, name)
            
        # Try ZKFPM_ prefix (Common on Linux SDK)
        if name.startswith("ZKFP_"):
            alt_name = name.replace("ZKFP_", "ZKFPM_")
            if hasattr(self.lib, alt_name):
                return getattr(self.lib, alt_name)
        
        return None

    def init_engine(self):
        if not self.lib: return -1
        
        # Some SDK versions require checking device count before Init
        get_count = self._get_func("ZKFPM_GetDeviceCount")
        if get_count:
            try:
                count = get_count()
                os.write(1, f"DEBUG: Device Count = {count}\n".encode())
            except Exception:
                pass

        func = self._get_func("ZKFP_Init")
        if not func: return -1
        try:
            res = func()
            os.write(1, f"DEBUG: Init Result = {res}\n".encode())
            return res
        except Exception as e:
            import traceback
            os.write(1, f"CRITICAL: {e}\n{traceback.format_exc()}\n".encode())
            return -2

    def terminate_engine(self):
        func = self._get_func("ZKFP_Terminate")
        if func:
            func()

    def open_device(self, index=0):
        func = self._get_func("ZKFP_OpenDevice")
        if not func: return False
        func.restype = ctypes.c_void_p
        try:
            self.hDevice = func(index)
            return self.hDevice is not None
        except Exception:
            return False

    def close_device(self):
        func = self._get_func("ZKFP_CloseDevice")
        if self.hDevice and func:
            func(self.hDevice)
            self.hDevice = None

    def get_db_handle(self):
        func = self._get_func("ZKFP_DBInit")
        if not func: return None
        func.restype = ctypes.c_void_p
        self.hDB = func()
        return self.hDB

    def free_db_handle(self):
        func = self._get_func("ZKFP_DBFree")
        if self.hDB and func:
            func(self.hDB)
            self.hDB = None


    def acquire_fingerprint(self):
        """Capture a fingerprint and return the template."""
        if not self.hDevice: return None
        
        func = self._get_func("ZKFP_AcquireFingerprint")
        if not func: return None
        
        # Buffer for template (usually 2048 bytes is enough for ZK)
        temp_buffer = (ctypes.c_ubyte * 2048)()
        temp_len = ctypes.c_int(2048)
        
        try:
            # signature: int ZKFP_AcquireFingerprint(void* hDevice, unsigned char* temp, int* tempLen)
            res = func(self.hDevice, temp_buffer, ctypes.byref(temp_len))
            if res == 0:
                # Success - return base64 encoded template
                return base64.b64encode(bytearray(temp_buffer[:temp_len.value])).decode('utf-8')
            return None
        except Exception as e:
            os.write(1, f"DEBUG: Capture Error: {e}\n".encode())
            return None

    def db_add(self, resident_id, template_b64):
        """Add a template to the SDK's internal DB cache."""
        if not self.hDB: return False
        
        func = self._get_func("ZKFP_DBAdd")
        if not func: return False
        
        try:
            template_data = base64.b64decode(template_b64)
            temp_len = len(template_data)
            temp_buffer = (ctypes.c_ubyte * temp_len)(*template_data)
            
            # signature: int ZKFP_DBAdd(void* hDB, int id, unsigned char* temp, int tempLen)
            res = func(self.hDB, int(resident_id), temp_buffer, temp_len)
            return res == 0
        except Exception:
            return False

    def db_identify(self, template_b64):
        """Identify a template against the DB cache."""
        if not self.hDB: return -1
        
        func = self._get_func("ZKFP_DBIdentify")
        if not func: return -1
        
        try:
            template_data = base64.b64decode(template_b64)
            temp_len = len(template_data)
            temp_buffer = (ctypes.c_ubyte * temp_len)(*template_data)
            
            uid = ctypes.c_int(0)
            score = ctypes.c_int(0)
            
            # signature: int ZKFP_DBIdentify(void* hDB, unsigned char* temp, int tempLen, int* id, int* score)
            res = func(self.hDB, temp_buffer, temp_len, ctypes.byref(uid), ctypes.byref(score))
            if res == 0:
                return uid.value
            return -1
        except Exception:
            return -1
