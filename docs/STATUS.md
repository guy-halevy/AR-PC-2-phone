# Current implementation status

Evidence updated 2026-09-09. The user's revised order implements AR and hands before real phone-to-PC stereo testing. Development source and binaries now exist; physical acceptance and a finished consumer installation flow remain pending.

| Component | Implementation and observed evidence |
| --- | --- |
| Shared math / diagnostic transport | 339 C++ checks and 15 Python tests pass locally and in CI |
| Native AR snapshot | Capture-time, freshness, freeze/recovery and fallback regression passes locally and in portable CI |
| ARCore-to-ALVR | Real Android lifecycle, calibrated origin and head/stereo-view hooks; arm64 derivative builds |
| MediaPipe/OpenCV hands | Local two-hand model inference and PnP standing-space conversion compiled into the APK |
| Encrypted hand protocol | v2 AES-GCM, random nonces, persistent sequence reservations, session/replay/schema checks |
| Desktop+ adapter / Windows input | Native panel snapshot/mutation integration, touch release state machine and pinch manipulation; Windows binaries build |
| Interaction regressions | 23 tests pass locally and on Windows CI, including authenticated reconnection after source-port changes |
| Android instrumentation | PASS: four production-component tests on API30 x86, with independent JUnit verification, in run 34365142111. No full headset runtime or physical camera test |
| Physical stereo, AR and hand accuracy | NOT RUN |
| Rendered hand skeleton / visual hover cursor | Not completed |
| Consumer installer / stable release signing | Not completed; current APK uses development debug signing |

## Current development validation

Validated protocol-v2 development builds (component tests and packaging, not physical acceptance):

- [Android APK build — passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142203): [download PhoneXR-Android-development](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142203/artifacts/10109827444), 73,605,476-byte ZIP including APK and corresponding source. APK signature, six required arm64 native libraries and model checksum passed.
- [Android component tests — passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142111): real bundled model load/blank frame, known-geometry PnP/rejection, AES-GCM/KeyStore/persistent sequences, and frame-clock checks. [Download reports](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142111/artifacts/10109682058).
- [Windows Desktop+ and bridge build — passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34363983157): [download PhoneXR-Windows-development](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34363983157/artifacts/10109167247), 18,285,322 bytes. Patched native build, 23 tests and packaged --help check passed.

The Android package and four-test component fixture use commit `ef70d745c297443ba8104e0c94dbde689bc90956`. The Windows package uses `6081ca775b8f592ab4fe7920505400f25194a057`; both implement protocol v2. These artifacts expire on 2026-09-23 and may require GitHub sign-in. Protocol v1 and v2 hand packages are incompatible.

PhoneXR APK: `PhoneVR-v2.0.0-beta-noGvr-debug.apk`, 45,758,422 bytes, application ID `org.phonexr.client`, debug signed. SHA-256: `945a109de9db7f0b0193fa5931cbb456788a93242ec5a6f6382c503a6e81301d`. It contains ALVR native glue/client, Cardboard, OpenCV, MediaPipe and ARCore JNI libraries plus the verified hand model. The earlier PhoneXR builds before the OpenCV loader correction are superseded.

The Android fixture executes production Java components on Android 11 x86. It does not execute the arm64 headset runtime or demonstrate detection of a real hand. The Windows regressions model injection contracts and include real loopback network cases; they do not establish physical desktop input behavior.

[Development setup](DEVELOPMENT_SETUP.md) explains the PC companion, Android installation, pairing, calibration and outstanding physical checks. [Review record](REVIEW.md) distinguishes observed corrections from security claims. [Dependency research](TRACKING_DEPENDENCIES.md) explains the free/open-source hand components and ARCore licensing limit.

## Build repairs established by CI

- Resolve sdkmanager through ANDROID_HOME because it is absent from the runner PATH.
- Use cargo-ndk 3.5.4: 0.9.0 does not exist for this package, and 3.5.5 was withdrawn. The crates.io API confirmed 3.5.4 is available and requires Rust 1.73 or newer.
- Pin Cardboard source, use stable ZXing, enforce ALVR Cargo.lock, and build arm64 with NDK r25c. The patched Cardboard SDK compiles.
- Build the standard Windows ALVR configuration without optional GPL FFmpeg dependencies, avoiding the upstream helper's moving download.

## Physical acceptance

The user explicitly authorized implementing AR and hand interaction before physical stereo testing. CI has no connected physical phone/headset, Windows gaming GPU or interactive SteamVR desktop. Compilation and synthetic tests cannot certify those checks.

The initial local-environment failures are preserved in the historical M0 audit. This file tracks subsequent GitHub work. Baseline artifacts are development components and must not be presented as the finished PhoneXR product.

Runtime procedure and unfilled results: [BASELINE_ACCEPTANCE.md](BASELINE_ACCEPTANCE.md).

## Downloadable baseline artifacts

Open a successful run above and download its named artifact from the Artifacts section. GitHub may require sign-in. Artifacts are retained for 14 days; the pinned workflows can rebuild them.

| Artifact | Run | ZIP bytes |
| --- | --- | --- |
| PhoneVR-arm64-baseline | 34195739292 | 44,637,120 |
| ALVR-v20.8.0-Windows-baseline | 34195828548 | 26,387,576 |
| DesktopPlus-v3.6-baseline | 34193762666 | 6,400,851 |

Android payload: PhoneVR-v2.0.0-beta-noGvr-debug.apk, 22,464,107 bytes. SHA256: `84310c60675f857fa1ff24fd6fff7086a2d63b406108d98898e2dccb31a27ab8`. APK v2 signature verification passed. The archive contains the expected AArch64 ELF libraries: native-lib-alvr, alvr_client_core and GfxPluginCardboard. This is debug signed and retains upstream analytics; it is not a privacy-complete PhoneXR release.

The preparation regression was reproduced and fixed: replacement text was a substring of the original for CPU targets and ZXing, causing an early return. The repaired patterns were applied to exact pinned source, checked for arm64-only/stable-ZXing/API26/locked-dependency output, and applied again to verify idempotence. The subsequent full APK build passed.

## Automated startup testing

[Run 34229435053](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34229435053) passed on Android 14/API34 x86_64: APK installation, launcher visibility, native ALVR activity creation and ten seconds of process survival. The observed foreground screen was Cardboard QrCodeCaptureActivity, the expected first-run viewer setup. This did not test streaming or physical tracking. [Run 34230007065](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34230007065) also passed the stricter assertion requiring ALVR or that exact viewer-setup screen, with crash checking scoped to the app process. Screenshots, UI/activity evidence and logs are attached to the run. Screenshots were captured in CI; a separate visual design review was not performed.

The arm64 phone baseline also rebuilt successfully in [run 34229435130](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34229435130) after the build scripts gained explicit ABI selection. See [startup coverage](ANDROID_STARTUP_TEST.md).
