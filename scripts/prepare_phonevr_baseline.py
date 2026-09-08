"""Apply narrow, checked build repairs to disposable pinned PhoneVR/Cardboard trees."""
import argparse
from pathlib import Path


def replace_once(path, before, after):
    text = path.read_text()
    if after in text:
        return
    if text.count(before) != 1:
        raise RuntimeError(f"Expected exactly one baseline pattern in {path}")
    path.write_text(text.replace(before, after, 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phonevr", type=Path)
    parser.add_argument("cardboard", type=Path)
    args = parser.parse_args()
    project = args.phonevr / "code/mobile/android/PhoneVR"
    app = project / "app/build.gradle"
    replace_once(app, "io.github.zxing-cpp:android:2.3.0-SNAPSHOT",
                 "io.github.zxing-cpp:android:2.3.0")
    replace_once(app, "minSdkVersion 24", "minSdkVersion 26")
    replace_once(app, "    defaultConfig {\n", "    defaultConfig {\n        ndk { abiFilters 'arm64-v8a' }\n")
    native = project / "ALVR/alvr/xtask/src/build.rs"
    replace_once(native,
                 '        "arm64-v8a",\n        "-t",\n        "armeabi-v7a",\n        "-t",\n        "x86_64",\n        "-t",\n        "x86",',
                 '        "arm64-v8a",')
    replace_once(native, 'let mut rust_flags = vec![];',
                 'let mut rust_flags = vec!["--locked"];')
    sdk = args.cardboard / "sdk/build.gradle"
    replace_once(sdk, "    compileSdk = 34", "    compileSdk = 34\n    ndkVersion '25.2.9519653'")
    replace_once(sdk, "            // abiFilters 'armeabi-v7a', 'arm64-v8a'",
                 "            abiFilters 'arm64-v8a'")
    print("Applied arm64 baseline build repairs; no ARCore or hand integration added.")


if __name__ == "__main__":
    main()
