"""Check that a baseline APK contains its required native components."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def verify(path, abi="arm64-v8a", phonexr=False):
    machine = {"arm64-v8a": 183, "x86_64": 62}[abi]
    required = (
        "libnative-lib-alvr.so",
        "libalvr_client_core.so",
        "libGfxPluginCardboard.so",
    )
    if phonexr:
        required += ("libopencv_java4.so", "libmediapipe_tasks_vision_jni.so", "libarcore_sdk_jni.so")
    with zipfile.ZipFile(path) as apk:
        bad = apk.testzip()
        if bad:
            raise ValueError(f"Corrupt APK member: {bad}")
        names = apk.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate APK members")
        for name in ("AndroidManifest.xml", "classes.dex"):
            if name not in names:
                raise ValueError(f"Missing {name}")
        for library in required:
            name = f"lib/{abi}/{library}"
            header = apk.read(name)[:20]
            if len(header) < 20 or header[:6] != b"\x7fELF\x02\x01":
                raise ValueError(f"Not a little-endian ELF64 library: {name}")
            if struct.unpack_from("<H", header, 18)[0] != machine:
                raise ValueError(f"Wrong ELF machine for {abi}: {name}")
        if phonexr:
            model = apk.read("assets/hand_landmarker.task")
            if hashlib.sha256(model).hexdigest() != "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1":
                raise ValueError("Wrong bundled hand model")
        abis = sorted({n.split('/')[1] for n in names if n.startswith('lib/') and n.endswith('.so')})
        if abis != [abi]:
            raise ValueError(f"Unexpected baseline ABIs: {abis}")
    return {
        "apk": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "abis": abis,
        "required_libraries": list(required),
        "runtime_tested": False,
        "product_release": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk_directory", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--abi", choices=("arm64-v8a", "x86_64"), default="arm64-v8a")
    parser.add_argument("--phonexr", action="store_true", help="Require AR/hand native libraries and verified model")
    args = parser.parse_args()
    apks = sorted(args.apk_directory.glob("*.apk"))
    if len(apks) != 1:
        raise SystemExit(f"Expected exactly one baseline APK, found {len(apks)}")
    report = verify(apks[0], args.abi, args.phonexr)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
