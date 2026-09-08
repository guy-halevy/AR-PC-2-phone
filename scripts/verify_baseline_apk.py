"""Check that a baseline APK contains its required arm64 native components."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def verify(path):
    required = (
        "libnative-lib-alvr.so",
        "libalvr_client_core.so",
        "libGfxPluginCardboard.so",
    )
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
            name = f"lib/arm64-v8a/{library}"
            header = apk.read(name)[:20]
            if len(header) < 20 or header[:6] != b"\x7fELF\x02\x01":
                raise ValueError(f"Not a little-endian ELF64 library: {name}")
            if struct.unpack_from("<H", header, 18)[0] != 183:
                raise ValueError(f"Not an AArch64 library: {name}")
        abis = sorted({n.split('/')[1] for n in names if n.startswith('lib/') and n.endswith('.so')})
        if abis != ["arm64-v8a"]:
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
    args = parser.parse_args()
    apks = sorted(args.apk_directory.glob("*.apk"))
    if len(apks) != 1:
        raise SystemExit(f"Expected exactly one baseline APK, found {len(apks)}")
    report = verify(apks[0])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
