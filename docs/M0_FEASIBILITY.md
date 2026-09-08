# PhoneXR — Milestone 0 feasibility audit

**Date:** 2026-09-07  
**Audience:** project owner and implementing engineers  
**Decision:** source-level integration is feasible, but the unmodified build/runtime gate has not passed. This is an incomplete M0 checkpoint, not a downloadable headset product.

The attached brief calls for Android + Windows, reuse of PhoneVR/ALVR and Desktop+, and a verified 6-DoF vertical slice before adding hands. The user owns Xiaomi, Apple and Windows devices, but exact models are unknown. This audit treats Android/Windows as the first target and does not assume universal compatibility.

## Versions verified from primary sources

| Project | Observed current release | Selected baseline / caveat |
| --- | --- | --- |
| PhoneVR | v2.0.0-beta, 2024-05-04 | Inspected and cloned master `7fdcebee4a662eb8a1c7a8b19774aac71820a772` from 2024-11-25; release maps to ALVR 20.8.0 |
| ALVR | v20.14.1, 2025-07-14 | Use PhoneVR's submodule `1d121fa7e0761ef26473c6b3f3fbd9b6051ce033`, corresponding to 20.8.0; latest pairing unverified |
| Desktop+ | v3.6, 2026-08-14 | Cloned `031d74d69f08411a9a9b1030d3d428ac02b93549`; release metadata says non-prerelease, body still contains a beta warning |
| ARCore Android SDK | 1.56.0, 2026-09-04 | Current source release; compatibility with PhoneVR's older Android build not resolved |
| MediaPipe | v1.0.0, 2026-07-28 | Google Maven metadata independently confirms tasks-vision 1.0.0; PhoneVR integration/model compatibility remains untested |
| OpenCV | 5.0.0, 2026-06-06 | Android release has a later 16 KB-page corrected asset; no OpenCV binary built here |
| OpenVR SDK | v2.15.6, 2026-03-27 | Inspected driver contract; use Desktop+'s bundled SDK baseline when building that project |

Primary releases: [PhoneVR](https://github.com/PhoneVR-Developers/PhoneVR/releases/tag/v2.0.0-beta), [ALVR current](https://github.com/alvr-org/ALVR/releases/tag/v20.14.1), [ALVR matching baseline](https://github.com/alvr-org/ALVR/releases/tag/v20.8.0), [Desktop+](https://github.com/elvissteinjr/DesktopPlus/releases/tag/v3.6), [ARCore](https://github.com/google-ar/arcore-android-sdk/releases/tag/1.56.0), [MediaPipe](https://github.com/google-ai-edge/mediapipe/releases/tag/v1.0.0), [OpenCV](https://github.com/opencv/opencv/releases/tag/5.0.0), [OpenVR](https://github.com/ValveSoftware/openvr/releases/tag/v2.15.6). The Android artifact version was checked against [Google Maven metadata](https://dl.google.com/dl/android/maven2/com/google/mediapipe/tasks-vision/maven-metadata.xml), last updated 2026-07-27. Sources accessed on the audit date. `upstream-lock.json` preserves selected revisions and unresolved inputs.

## Integration findings

**Head pose has an existing path.** PhoneVR's native `getPose()` supplies Cardboard orientation and drops positional motion. Its update path sends both HMD motion and stereo view poses through an ALVR interface that already supports translation and orientation. Replace all related pose paths consistently; remove the fixed floor-offset assumption from the relevant helper. A second independent HMD driver is not the right approach because the streaming driver already owns the active HMD. [PhoneVR native implementation](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/app/src/main/cpp/alvr_main.cpp), [ALVR C API](https://github.com/alvr-org/ALVR/blob/1d121fa7e0761ef26473c6b3f3fbd9b6051ce033/alvr/client_core/src/c_api.rs), [OpenVR driver API](https://github.com/ValveSoftware/openvr/blob/v2.15.6/docs/Driver_API_Documentation.md).

**ARCore can own the camera once.** Obtain a camera image through `Frame.acquireCameraImage`, capture its matching pose/intrinsics, and close bounded outstanding images. Physical camera coordinates and display orientation are different. ARCore frame timestamps have an unspecified time base, so they cannot simply be compared to ALVR's target clock. [Frame API](https://developers.google.com/ar/reference/java/com/google/ar/core/Frame), [Camera API](https://developers.google.com/ar/reference/java/com/google/ar/core/Camera), [official ML integration](https://developers.google.com/ar/develop/java/machine-learning).

**Origin handling needs correction.** Engineering inference: calibrate a session anchor into standing space and use the anchor's updated pose to transform the camera/HMD. Re-estimating alignment from the same SteamVR pose derived from ARCore is circular. Local anchors alone do not restore physical coordinates after a session restart. The proposed composition and its limits are explicit in ARCHITECTURE.md and tested in shared/math/pose.hpp. [Anchor behavior](https://developers.google.com/ar/develop/anchors).

**Desktop+ needs a narrow fork.** Its private dashboard/UI IPC is not an established general sidecar API. Effective panel transforms, validated crop, capture HWND and dimensions are accessible inside the project. World-space updates must go through its origin-aware configuration path. A new versioned local adapter is proposed; it has not been implemented. [IPC declaration](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/InterprocessMessaging.h), [OverlayManager](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/OverlayManager.cpp), [configuration](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/ConfigManager.h).

**Proportional touch mapping needs capture metadata.** A captured Windows window may include its frame. Map panel UV through the validated crop and DWM capture bounds, then into desktop pixels; do not assume the whole texture is the client rectangle. Preserve DPI and monitor coordinate context. [Desktop+ capture/input code](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/DesktopPlus/OutputManager.cpp).

**Windows touch has specific release rules.** UP must use the preceding successful UPDATE's position. Return-value handling matters; injection is desktop-coordinate input, not guaranteed background-HWND delivery. Privileged target handling remains a real Windows test. The ordinary mouse fallback cannot bypass UIPI. [InjectTouchInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-injecttouchinput), [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput).

**Monocular depth remains the main experiment.** MediaPipe's hand-centered metric geometry does not supply absolute AR-world position. PnP can estimate object-to-camera pose from matching 2D/3D points and intrinsics, but reprojection error is not a guarantee of stable metric fingertip depth. Device measurements, scale calibration, and hand visibility remain necessary. The hand stage is intentionally not implemented before M1. [MediaPipe hand outputs](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/android), [PnP contract](https://docs.opencv.org/4.13.0/d5/d1f/calib3d_solvePnP.html).

## Build evidence from this workspace

| Attempt | Observed outcome |
| --- | --- |
| Source checkout | PhoneVR, matching ALVR submodule and Desktop+ cloned and exact revisions verified |
| Initial Android toolchain | No SDK/NDK/Gradle/Rust; system Java needed explicit library location; no javac |
| Toolchain recovery | Downloaded and checksum-verified Temurin JDK 17.0.20.1+1 and Gradle 8.7; javac and Gradle launch verified with workspace-local library/temp paths |
| Android baseline build | Wrapper network download failed; local Gradle reached project configuration but could not resolve Spotless 6.20.0; no APK generated |
| ALVR build invocation | Cannot launch cargo; no Rust compiler installed |
| Desktop+ build invocation | Cannot launch MSBuild; Windows SDK/runtime and SteamVR desktop absent |
| Portable math | Compiles with warnings as errors; 339 checks pass |
| Diagnostic protocol | 15 tests pass, including real loopback and modeled Windows receive-error regression |
| Documented replay CLI | Fresh pairing, separate receiver/sender processes, synthetic poses and final pause verified |

The Spotless 6.20.0 marker POM was separately accessible through the normal HTTP download path, so the Gradle failure does not establish that the plugin version is nonexistent. Logs are included under docs/. The Android/Windows/XR stack is not built or run. Missing SDK/native dependencies would still need resolution after the current Gradle failure. Builds must not be represented as successful simply because source was cloned or core tests passed.

## Compatibility, privacy and licensing

Google certifies individual devices; an unspecified Xiaomi model/ROM does not establish ARCore availability. The iOS list does not make PhoneVR's Android client an iPhone application. The design requires a separate iOS client if that platform is pursued. [Supported device scope](https://developers.google.com/ar/devices).

PhoneVR itself is GPL v3, as is Desktop+; ALVR is MIT. Keep forks and original code separate and preserve the appropriate source/notices. PhoneVR's inspected Gradle configuration includes Firebase Analytics, which must be removed for the requested local-only derivative. Its preparation also uses moving Cardboard and Rust dependency inputs, so reproducibility remains unfinished. [PhoneVR license](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/LICENSE), [Desktop+ license](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/LICENSE), [ALVR license](https://github.com/alvr-org/ALVR/blob/1d121fa7e0761ef26473c6b3f3fbd9b6051ce033/LICENSE), [PhoneVR Gradle](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/app/build.gradle), [preparation script](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/prepare-alvr-deps.sh).

## Decision and next gate

Continue with the pinned reuse architecture. Do not implement the hand stack or claim install-only completion until the baseline and real ARCore-to-SteamVR 6-DoF slice pass. The next concrete need is an Android-capable build environment plus a Windows build/test environment and the actual device model. An explicitly selected GitHub repository could provide a place for native build workflows; no target repository was supplied or modified in this session.

Research stopped after upstream interfaces and consequential risks had primary support and build attempts exposed the current practical gates. Remaining evidence gaps are binary builds, Android dependency/model compatibility, mounted-phone camera/decoder concurrency, physical tracking accuracy, capture/input behavior, and all 14 MVP tests. These are listed as unresolved, not inferred successes.
