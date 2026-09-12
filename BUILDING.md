# Building PhoneXR and its baselines

The workflows build PhoneXR development APK/Windows packages and their pinned upstream baselines. There is no finished consumer installer yet. [Current results](docs/STATUS.md) distinguish compilation from runtime acceptance.

## Portable checks

Requires Python 3.10+ and a C++17 g++ or clang++ compiler:

```sh
python tools/run_checks.py
```

Set CXX to select a compiler. The runner writes build/checks.log and fails on a compilation or test error. The separate windows-protocol.yml workflow runs the Python protocol suite on Windows Server 2022.

## Native builds on GitHub

Open the repository's Actions tab and select the corresponding workflow. Pushes to each workflow trigger it, and workflow_dispatch permits a manual run. Successful runs expose a downloadable artifact for 14 days. These are development packages; SteamVR and device operation are not certified by compilation.

| Workflow | Build | Packaged evidence |
| --- | --- | --- |
| Windows PhoneXR adapter and bridge | Patched Desktop+ v3.6 and packaged Python bridge | Executables, corresponding source, interaction test logs and notices |
| Android PhoneXR development | ARCore/MediaPipe/OpenCV arm64 derivative | Debug APK, corresponding source and build record |
| Android PhoneXR integration tests | API30 x86 component fixture using production Java sources | JUnit XML, HTML report and required-test verification |
| Windows DesktopPlus baseline | Desktop+ v3.6, MSBuild Release x64 on windows-2022 | Binaries, source archive, GPL license |
| Windows ALVR matching streamer | ALVR 20.8.0 revision embedded in PhoneVR, Rust 1.85.1 | Dashboard/driver, source, lockfile patch, MIT license |
| Android PhoneVR baseline | PhoneVR arm64 noGvr debug, native ALVR client, pinned Cardboard | APK when successful, corresponding source, preparation script, notices |

All checkout and upload actions are pinned to commit SHAs with read-only repository permissions. No signing secrets are needed for these debug builds.

### Android

The workflow installs JDK 17, SDK 34, NDK 25.2.9519653, Rust 1.85.1, cargo-ndk 3.5.4 and cbindgen 0.26.0. It uses each pinned project's Gradle wrapper. Run scripts/prepare_phonevr_baseline.py only on disposable checkouts at the documented revisions; it checks its source patterns before edits. See [Android build notes](docs/android-baseline-notes.md).

The first artifact supports arm64 Android API 26+, retains upstream analytics, and uses debug signing. It adds no ARCore or hands. The upstream moving preparation script is not run.

### Matching Windows streamer

The workflow builds the standard Windows streamer without optional GPL FFmpeg support. This avoids the upstream dependency helper's moving FFmpeg download. It changes the xtask reproducible argument to enforce the existing Cargo.lock and includes that patch with the source archive.

### Desktop+

The workflow restores the pinned source's NuGet dependencies and builds src/DesktopPlus.sln with MSBuild. See [upstream requirements](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/README.md). The separate Windows PhoneXR workflow applies `desktopplus-integration/prepare_desktopplus.py` before compilation and packages the real `windows-bridge` executable.

## Local baseline source

Run python tools/fetch_upstreams.py to fetch the upstream-lock.json revisions. Existing directories are verified and never reset. The helper does not install dependencies or launch VR. Initial Linux-only build attempts were blocked by local Java networking and missing native toolchains; GitHub Windows and Android builds supersede those environment limitations.

## Release gate

The user authorized ARCore and hand implementation before physical stereo testing. A release still requires the real phone and Windows GPU to pass stereo, 6-DoF and hand acceptance tests. Production APK signing must use a stable privately held key; upstream test keys are not release identities. Package corresponding source and license notices with all derivatives.

## PhoneXR derivative preparation

After baseline preparation, run `python scripts/prepare_phonexr.py PATH_TO_PHONEVR` on the disposable checkout. It checks patch anchors, copies the tracked Java/native/test sources, adds exact ARCore/MediaPipe/OpenCV dependencies and downloads the official hand model with SHA-256 verification. It removes upstream Firebase initialization/dependencies, disables crash-reporter initialization and app backup, and uses application ID `org.phonexr.client`.

The development workflows run this integration automatically. Android instrumentation selects the five PhoneXR tests, propagates failures, and independently validates their JUnit XML. Upstream screenshot tests needing a streaming setup are not part of this component suite. See docs/REVIEW.md for the earlier inherited failure-suppression defect.

The component test fixture under `android-client/test-app` uses the exact production Java sources and model on API30 x86. MediaPipe Tasks 0.10.14 does not ship an x86_64 native library. This fixture therefore tests the real model, OpenCV geometry, encryption and clock components on its supported emulator ABI, and adds a native EGL/GLES3 probe for the actual hand renderer, without claiming to execute the full ALVR/ARCore headset runtime. The separate arm64 APK gate checks all six required native libraries and the model hash.
