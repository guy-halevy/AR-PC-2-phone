# Current implementation status

Repository: guy-halevy/AR-PC-2-phone. Evidence updated 2026-09-08.

| Component | Observed evidence |
| --- | --- |
| Shared C++ math | 339 checks pass locally and in Linux CI |
| Diagnostic protocol | 15 tests pass locally and on [Windows CI](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762726) |
| Desktop+ v3.6 baseline | [Release x64 build passed](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762666); binaries and corresponding source uploaded |
| PhoneVR baseline | SDK/tool setup and pinned Cardboard build passed; native client compilation running |
| Matching ALVR 20.8.0 streamer | Windows native compilation running |
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
