# Android baseline build

This is a build-repaired PhoneVR baseline, not the PhoneXR product. It adds no ARCore or hand tracking and retains upstream behavior, including upstream analytics. Do not present it as the requested privacy-complete client.

Source pins: PhoneVR `7fdcebee4a662eb8a1c7a8b19774aac71820a772`, its ALVR 20.8.0 submodule, and nift4/Cardboard `13bc289daaf89e77fea76c616a15d85e7b2e91aa`.

The preparation script replaces PhoneVR's ZXing snapshot with the stable 2.3.0 used by the pinned Cardboard source, selects arm64 for this first device build, pins Cardboard's NDK to PhoneVR's r25c, and requires ALVR's existing Cargo.lock for the native client build. The moving upstream preparation script and its cargo update are not run.

Tools: JDK 17, Gradle versions from each pinned wrapper, SDK 34, NDK 25.2.9519653, Rust 1.85.1, cargo-ndk 3.5.4, cbindgen 0.26.0. CI resolves and compiles these rather than assuming success. This first artifact is arm64 only, debug signed, and requires Android API 26 for the ALVR native path. It is not a universal phone release.

[Run 34195739292](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34195739292) passed compilation, APK native-payload verification and APK v2 signature verification. Actual installation, stereo display and ALVR connectivity remain untested on a phone and must pass before the ARCore integration stage.
