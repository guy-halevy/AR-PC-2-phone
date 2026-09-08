"""Install and exercise baseline startup on a disposable Android emulator."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = "viritualisres.phonevr"


def adb(*args, check=True):
    return subprocess.run(["adb", *args], check=check, capture_output=True,
                          text=True, timeout=45).stdout


def capture(output, label):
    result = subprocess.run(["adb", "exec-out", "screencap", "-p"],
                            check=True, capture_output=True, timeout=30)
    (output / f"{label}.png").write_bytes(result.stdout)
    activity = adb("shell", "dumpsys", "activity", "activities")
    (output / f"{label}-activities.txt").write_text(activity)
    return activity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk_directory", type=Path)
    parser.add_argument("--output", type=Path, default=Path("smoke-evidence"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"passed": False, "physical_device": False,
              "stereo_stream_tested": False, "stages": []}
    try:
        apks = list(args.apk_directory.glob("*.apk"))
        if len(apks) != 1:
            raise RuntimeError(f"Expected one APK, found {len(apks)}")
        abi = adb("shell", "getprop", "ro.product.cpu.abi").strip()
        if abi != "x86_64":
            raise RuntimeError(f"Expected disposable x86_64 emulator, found {abi}")
        report["abi"] = abi
        report["api"] = adb("shell", "getprop", "ro.build.version.sdk").strip()
        result = adb("install", "-r", "-g", str(apks[0]))
        if "Success" not in result:
            raise RuntimeError(f"APK installation did not succeed: {result}")
        report["stages"].append("installed")
        adb("logcat", "-c")
        launch = adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.InitActivity")
        (args.output / "launch.txt").write_text(launch)
        if "Status: ok" not in launch:
            raise RuntimeError(f"Launcher failed: {launch}")
        time.sleep(3)
        activity = capture(args.output, "launcher")
        if not any("ResumedActivity" in line and ".InitActivity" in line
                   for line in activity.splitlines()):
            raise RuntimeError("Launcher is not the resumed activity")
        report["stages"].append("launcher_visible")
        adb("shell", "uiautomator", "dump", "/sdcard/phonexr-smoke.xml")
        xml = adb("shell", "cat", "/sdcard/phonexr-smoke.xml")
        (args.output / "launcher.xml").write_text(xml)
        button = next((n for n in ET.fromstring(xml).iter("node")
                       if n.get("resource-id") == f"{PACKAGE}:id/alvr_streamer"), None)
        if button is None:
            raise RuntimeError("ALVR launch button missing from visible UI")
        bounds = list(map(int, re.findall(r"\d+", button.get("bounds", ""))))
        if len(bounds) != 4:
            raise RuntimeError("ALVR button has invalid bounds")
        adb("shell", "input", "tap", str((bounds[0]+bounds[2])//2),
            str((bounds[1]+bounds[3])//2))
        pid = None
        for _ in range(10):
            time.sleep(1)
            current = adb("shell", "pidof", PACKAGE, check=False).strip()
            if not current or (pid is not None and current != pid):
                raise RuntimeError("Application exited or restarted after ALVR selection")
            pid = current
        activity = capture(args.output, "after-alvr-selection")
        resumed = [line.strip() for line in activity.splitlines() if "ResumedActivity" in line]
        report["resumed_activity"] = resumed
        if not resumed or any("ErrorReporting" in line for line in resumed):
            raise RuntimeError("ALVR selection reached an error screen")
        log = adb("logcat", "-d", "-v", "threadtime")
        if "onCreate ALVRActivity" not in log:
            raise RuntimeError("Native streaming activity was never created")
        if re.search(r"FATAL EXCEPTION|Fatal signal|UnsatisfiedLinkError", log):
            raise RuntimeError("Runtime log contains a fatal error; inspect logcat.txt")
        report["stages"].append("alvr_selection_survived_10_seconds")
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (args.output / "logcat.txt").write_text(adb("logcat", "-d", "-v", "threadtime", check=False))
        (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
