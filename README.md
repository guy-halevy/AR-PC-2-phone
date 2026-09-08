# PhoneXR Spatial Desktop

**Development checkpoint — not an installable XR product.**

The goal is an Android phone headset and Windows spatial desktop with world-fixed panels and direct hand touch. This repository contains a source-level feasibility audit and supplies tested coordinate math and a diagnostic pose transport. It does **not** include a working PhoneXR APK, Windows executable, Desktop+ patch, camera tracking, video stream, or input injection. Desktop+ now compiles on Windows and the protocol suite passes Windows CI. PhoneVR and the matching ALVR streamer also build successfully, with baseline downloads linked below. The 6-DoF SteamVR vertical slice has not passed.

[Baseline downloads, verified build results, and next gates](docs/STATUS.md)

## What runs now

- Dependency-free C++17 rigid transforms, calibrated anchor/HMD composition, camera-axis conversion, and panel UV geometry.
- Python 3.10+ authenticated 100-byte diagnostic pose packets, sequence/session checks, a receipt watchdog, and synthetic UDP replay.
- Automated math, protocol, and loopback tests. Run `python tools/run_checks.py` with a C++17 compiler available.

Read [M0 feasibility](docs/M0_FEASIBILITY.md), [architecture](ARCHITECTURE.md), [build instructions](BUILDING.md), [test evidence](TESTING.md), and [roadmap](ROADMAP.md).

## First supported target

An ARCore-supported Android phone, a headset with an unobstructed rear camera, and a Windows gaming PC compatible with the pinned ALVR/SteamVR stack. Xiaomi model and ROM, GPU model, and headset geometry are still unknown. iPhone requires a separate client. Universal phone/PC compatibility has not been established.

## Diagnostic replay

From this directory, create fresh local pairing material:

```sh
python shared/protocol/pose_packet.py create-pairing --key-file pairing.key --session-file pairing.session
```

In one terminal:

```sh
python tools/packet-viewer/receive.py --key-file pairing.key --session-file pairing.session
```

In another:

```sh
python tools/replay-tool/replay.py --key-file pairing.key --session-file pairing.session
```

The receiver prints synthetic camera motion and a final paused state. Nothing changes in SteamVR or Windows. Use a fresh pair for a new receiver session; do not package these files. The default address is loopback. There is no automatic phone discovery, secure pairing UI, or network clock synchronization yet.

## Delivery status

This archive is source and development tooling. A phone download alone cannot fulfill this design: the Windows companion and streaming stack are also required. The end-user installation path will be documented only after real packages and hardware acceptance tests exist.
