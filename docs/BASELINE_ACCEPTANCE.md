# Milestone 0 runtime acceptance

Status: **NOT RUN ON HARDWARE**. Complete this record with the baseline artifacts before starting ARCore integration, as required by the product brief. A CI build or simulated pose packet is not a runtime pass.

## Required setup record

Record phone model, Android/ROM version, CPU ABI, Windows version, GPU and driver, SteamVR version, headset model/mount orientation, and network type. Record the build run and APK SHA256 from apk-verification.json. Do not include account credentials, pairing keys or device serial numbers.

The first Android build is arm64, API 26+, noGvr, and debug signed. Camera access, gyroscope and OpenGL ES 3.1 are declared by its upstream manifest. ARCore support must be checked separately before Milestone 1. The Windows package must match ALVR 20.8.0; current ALVR releases are not interchangeable with this client.

## Runtime sequence

1. On the Windows PC, use the matching ALVR dashboard with the installed SteamVR stack. Keep the streamer package's driver and resource files together.
2. Install the baseline APK on the Android phone. Open PhoneVR and choose its ALVR path. Connect through ALVR's normal setup flow on the same trusted local network.
3. While seated, confirm that the headset displays separate left/right views, head rotation moves the rendered view in the correct direction, and audio behaves as configured. Record any decoder or connection errors.
4. Start Desktop+ and display an ordinary desktop window. Confirm that its capture appears inside SteamVR. The baseline has no PhoneXR hand-touch bridge.
5. Disconnect and reconnect the phone. Confirm that the stream recovers without needing to reinstall software. Observe at least ten minutes of operation and record freezes, crashes, frame rate and temperature warnings if available.

Follow the upstream [PhoneVR setup for this pinned source](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/README.md) and the matching [ALVR source documentation](https://github.com/alvr-org/ALVR/tree/1d121fa7e0761ef26473c6b3f3fbd9b6051ce033). Do not install the legacy PVRServer driver for this ALVR baseline.

## Evidence record

| Check | Result | Evidence / observed problem |
| --- | --- | --- |
| APK installs and launches | NOT RUN | |
| Matching streamer connects | NOT RUN | |
| Stereo display and head rotation | NOT RUN | |
| Desktop+ capture in SteamVR | NOT RUN | |
| Disconnect/reconnect recovery | NOT RUN | |
| Ten-minute baseline session | NOT RUN | |

The next stage adds ARCore head position. Its separate exit test is real 30–50 cm head translation in SteamVR with consistent stereo view poses. Hands remain gated until that test passes. No positional tracking or direct touch is expected from these baseline packages.
