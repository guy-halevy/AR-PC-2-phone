# Current implementation status

Repository: guy-halevy/AR-PC-2-phone. Evidence updated 2026-09-08.

| Component | Observed evidence |
| --- | --- |
| Shared C++ math | 339 checks pass locally and in Linux CI |
| Diagnostic protocol | 15 tests pass locally and on [Windows CI](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762726) |
| Desktop+ v3.6 baseline | [Release x64 build passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762666); binaries and corresponding source uploaded |
| PhoneVR baseline | [APK build and verification passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34195739292); APK and corresponding source uploaded |
| Matching ALVR 20.8.0 streamer | [Windows build and packaging passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34195828548); dashboard, driver and source uploaded |
| ARCore-to-SteamVR integration | Not implemented; gated on baseline runtime |
| MediaPipe/PnP hands | Not implemented; gated on the 6-DoF slice |
| Desktop+ adapter / Windows touch | Design and shared geometry only |
| Finished PhoneXR APK / Windows installer | Not available |

## Build repairs established by CI

- Resolve sdkmanager through ANDROID_HOME because it is absent from the runner PATH.
- Use cargo-ndk 3.5.4: 0.9.0 does not exist for this package, and 3.5.5 was withdrawn. The crates.io API confirmed 3.5.4 is available and requires Rust 1.73 or newer.
- Pin Cardboard source, use stable ZXing, enforce ALVR Cargo.lock, and build arm64 with NDK r25c. The patched Cardboard SDK compiles.
- Build the standard Windows ALVR configuration without optional GPL FFmpeg dependencies, avoiding the upstream helper's moving download.

## Runtime gate

The brief requires the unmodified stereo stack to run before ARCore work, and real 6-DoF movement before hands. CI has no connected phone, headset, Windows gaming GPU or interactive SteamVR desktop. Compilation and synthetic protocol tests cannot satisfy those checks.

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
