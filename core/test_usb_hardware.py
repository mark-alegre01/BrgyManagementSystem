import usb.core
import usb.util
import sys

def test_hardware():
    VID = 0x1b55
    PID = 0x0124
    
    print(f"Searching for ZK9500 (ID {VID:04x}:{PID:04x})...")
    
    # Find device
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    
    if dev is None:
        print("Error: ZK9500 device NOT found on USB bus.")
        print("Please ensure it is plugged in and check 'lsusb' output.")
        return
    
    print("Success: ZK9500 hardware DETECTED!")
    
    try:
        # Check if we can read the device descriptor
        print(f"Device Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
        print(f"Device Product: {usb.util.get_string(dev, dev.iProduct)}")
        
        # Try to set configuration (requires udev rule permissions)
        try:
            dev.set_configuration()
            print("Success: Device configuration SET (permissions OK).")
        except usb.core.USBError as e:
            if e.errno == 13:
                print("Error: Permission denied. Please ensure the udev rules are installed and correctly triggered.")
            else:
                print(f"Error setting configuration: {e}")
                
    except Exception as e:
        print(f"Successfully detected, but could not read details: {e}")
        print("This is usually a permission issue. Please ensure udev rules are set correctly.")

if __name__ == "__main__":
    test_hardware()
