import time
import pythoncom
import win32com.client

PROGID = "ZKFPEngXControl.ZKFPEngX"

class ZkEvents:
    def OnImageReceived(self):
        print("Event: OnImageReceived")

    def OnFeatureInfo(self, AQuality):
        print("Event: OnFeatureInfo quality =", AQuality)

    def OnFingerTouching(self):
        print("Event: OnFingerTouching")

    def OnFingerLeaving(self):
        print("Event: OnFingerLeaving")

    def OnCapture(self, ActionResult, ATemplate):
        # Some SDKs fire OnCapture with template data
        print("Event: OnCapture result =", ActionResult)
        if ATemplate:
            try:
                print("Template length =", len(ATemplate))
            except Exception:
                print("Template (non-sized type) =", type(ATemplate))

    def OnEnroll(self, ActionResult, ATemplate):
        print("Event: OnEnroll result =", ActionResult)
        if ATemplate:
            try:
                print("Enroll template length =", len(ATemplate))
            except Exception:
                print("Enroll template (non-sized type) =", type(ATemplate))

    def OnTemplate(self, ATemplate):
        if ATemplate:
            try:
                print("Event: OnTemplate length =", len(ATemplate))
            except Exception:
                print("Event: OnTemplate type =", type(ATemplate))

    def OnFeature(self, ATemplate):
        if ATemplate:
            try:
                print("Event: OnFeature length =", len(ATemplate))
            except Exception:
                print("Event: OnFeature type =", type(ATemplate))

    def OnError(self, ErrorCode):
        print("Event: OnError code =", ErrorCode)

def main():
    # Create COM object with event sink
    zk = win32com.client.DispatchWithEvents(PROGID, ZkEvents)

    r = zk.InitEngine()
    print("InitEngine:", r)
    print("EngineValid:", getattr(zk, "EngineValid", None))
    print("FPEngineVersion:", getattr(zk, "FPEngineVersion", None))
    print("SensorCount:", getattr(zk, "SensorCount", None))
    print("SensorIndex:", getattr(zk, "SensorIndex", None))
    print("SensorSN:", getattr(zk, "SensorSN", None))
    print("IsSupportAuxDevice:", getattr(zk, "IsSupportAuxDevice", None))
    print("EnrollCount:", getattr(zk, "EnrollCount", None))
    print("EnrollIndex:", getattr(zk, "EnrollIndex", None))

    # Try starting capture
    try:
        rc = zk.BeginCapture()
        print("BeginCapture:", rc)
    except Exception as e:
        print("BeginCapture error:", e)

    try:
        re = zk.BeginEnroll()
        print("BeginEnroll:", re)
    except Exception as e:
        print("BeginEnroll error:", e)

    print("Now touch the sensor. Waiting 60 seconds for events...")
    end = time.time() + 60
    while time.time() < end:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.05)

    try:
        zk.CancelCapture()
    except Exception:
        pass

    try:
        zk.CancelEnroll()
    except Exception:
        pass

    try:
        zk.EndEngine()
    except Exception:
        pass

    print("Done.")

if __name__ == "__main__":
    main()