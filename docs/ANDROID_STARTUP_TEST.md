# Automated Android startup check

The android-smoke.yml workflow builds the same pinned PhoneVR/Cardboard/ALVR source for x86_64, verifies its native payload and signature, and installs it on an Android 14 (API 34) emulator. The downloadable phone package remains arm64.

The check exercises the real launcher and taps its ALVR button using the visible UI hierarchy. It requires the ALVR activity or Cardboard viewer-setup activity to remain in the foreground, a stable process for ten seconds, and no app-process fatal errors. Screenshots, activity dumps, UI XML, app logs, full emulator logs and a JSON result are uploaded even when the check fails after emulator launch.

This establishes only installation and startup behavior on that emulator configuration. It does not establish actual phone compatibility, successful headset calibration, video decoding, stereo streaming, head tracking, camera quality, latency or hand interaction. The workflow does not mark Milestone 0's physical stereo test complete.

Reproduce on a disposable x86_64 emulator after building the matching APK:

```sh
python scripts/android_startup_smoke.py path/to/apk/directory --output smoke-evidence
```

The script installs the APK with its requested runtime permissions granted. Permission-denial flows and lifecycle recovery require additional tests before release. It must not be pointed at a personal phone as a substitute for the separately documented physical baseline acceptance.

See STATUS.md and TESTING.md for observed results; workflow presence alone is not a pass.
