# PhoneXR Spatial Desktop

Android phone headset + Windows spatial desktop. Development implementations now include ARCore head tracking, local MediaPipe/OpenCV hand pose estimation, encrypted hand transport, a patched Desktop+ panel adapter, Windows touch, pinch-based panel manipulation, a stereo hand-skeleton display and a per-user Windows companion installer.

The Android APK and Windows companion compile in CI. Physical stereo streaming, alignment, hand accuracy, latency and Windows input acceptance are still unverified. This is a development build, not a finished consumer release. The user's revised milestone order puts physical stereo acceptance after AR and hand implementation.

[Current evidence and downloads](docs/STATUS.md) · [Development setup](docs/DEVELOPMENT_SETUP.md) · [Dependency research](docs/TRACKING_DEPENDENCIES.md) · [Review record](docs/REVIEW.md)

## Implemented

- ARCore owns the camera and publishes capture-time head poses to both ALVR head and stereo-view paths. Recenter anchors the standing-space origin; settings expose eye height, camera-to-eye offset and hand scale.
- MediaPipe runs on-device with one in-flight image. OpenCV estimates camera-relative hand position, rejects invalid geometry and transforms landmarks into the same standing space.
- AES-GCM hand packets authenticate the session, sequence and random nonce. Pairing material is encrypted with Android KeyStore. Raw camera images are not sent by this pipeline.
- Desktop+ exports validated panel geometry and accepts revision-checked manipulation commands. The Windows bridge implements contact debounce, hysteresis, loss release, single-contact touch and border/two-hand pinch manipulation. Input starts disabled.
- Portable C++ math and protocol checks, Windows interaction regressions, and Android instrumentation tests cover bounded software behavior. See the evidence record for test limitations.

## Supported development target

An ARCore-supported Android phone (arm64, Android 8/API26 or newer), a headset with an unobstructed rear camera, and a Windows gaming PC compatible with the pinned ALVR 20.8.0/SteamVR stack. iPhone needs a separate client. Device compatibility has not been established for the user's phone.

A phone download alone cannot provide a Windows spatial desktop: the PC companion, streaming software, pairing and calibration are also required. Development packages contain binaries and corresponding source; GitHub artifact downloads may require sign-in.

## Local checks

Run `python tools/run_checks.py` for shared math and diagnostic transport. Install `windows-bridge/requirements.txt`, then run `python -m unittest discover -s tests/interaction -v` for interaction regressions. These checks do not move a physical pointer or certify tracking accuracy.
