# Building the checkpoint

This document distinguishes the portable development tools from the unbuilt XR application. There is no PhoneXR APK or Windows product installer to install yet.

## Portable checks

Requirements: Python 3.10+ and a C++17 `g++` or `clang++` compiler. There are no pip or npm dependencies for the protocol, replay, or native math tests.

```sh
python tools/run_checks.py
```

Set `CXX` to a compiler executable if automatic detection is unsuitable. The runner writes `build/checks.log` and stops on a failed compilation or test. On Windows, a compatible MinGW/Clang compiler is required for this particular helper; it is not an MSVC build wrapper. Only Linux execution was verified here.

The diagnostic replay command sequence is in [README.md](README.md). The HTML Code Lab can be opened directly in a browser; only JavaScript examples are enabled, using local browser execution.

## Pinned upstream baseline

The source audit cloned PhoneVR and Desktop+ and initialized PhoneVR's submodules. The selected source revisions are recorded in `upstream-lock.json`; no binary build success is implied by a successful clone.

Use `python tools/fetch_upstreams.py` to fetch those revisions into a new `third_party/` directory. Existing directories are verified and never reset. This helper fetches source only; it does not run upstream scripts, install software, change firewall rules, or start VR.

### PhoneVR / ALVR

The inspected [PhoneVR build](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/app/build.gradle) uses SDK 34, target SDK 33, minimum SDK 24, NDK `25.2.9519653`, Kotlin `1.9.0`, Android Gradle plugin `8.3.1`, and [Gradle 8.7](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/gradle/wrapper/gradle-wrapper.properties). JDK 17 is the baseline used by upstream CI.

Before a reproducible build, supply Android SDK/NDK, compatible Rust Android targets, and the matching ALVR/Cardboard native libraries. The [upstream preparation script](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/prepare-alvr-deps.sh) runs `cargo update` and fetches a moving Cardboard master. A reproducible fork must pin these inputs rather than relabel that script as a locked installer.

The attempted unmodified Android target was:

```sh
./gradlew :app:assembleNoGvrDebug --no-daemon --console=plain
```

The wrapper could not download using the Java networking path in this workspace. A checksum-verified local JDK and Gradle distribution recovered configuration; the build then stopped resolving Spotless `6.20.0`. See `docs/android-build-local-gradle.log`. No APK was generated. The missing Android SDK/NDK and Rust/native prerequisites remain additional gates after that resolution issue.

ALVR's pinned Rust project was inspected and a build invocation attempted; `cargo` is unavailable in this environment. This is a blocked attempt, not a compilation failure in ALVR source. See `docs/alvr-build.log`.

### Desktop+

The documented upstream build uses Visual Studio on Windows with C++/WinRT and the Windows SDK. This Linux workspace has neither MSBuild nor a Windows desktop/SteamVR session. The attempted `msbuild src/DesktopPlus.sln /p:Configuration=Release /p:Platform=x64` cannot launch. See [upstream build requirements](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/README.md) and `docs/desktopplus-build.log`.

## Future release packaging

After M0/M1 and device tests pass, produce a signed Android APK and a tested Windows companion package from pinned source. Keep signing credentials outside the repository and archive. Provide matching source/license notices for derivatives. Verify APK installation and launch on the actual Android device; verify Windows capture/input on its desktop session. None of these release steps has been completed.

The GitHub workflow supplied here tests only the portable checkpoint. It has not been executed on GitHub in this conversation, and is not an Android or Windows release pipeline.
