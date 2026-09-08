# Roadmap and release gates

No stage is complete solely because its source code exists. Follow the attached brief's order.

| Stage | Exit evidence | Current state |
| --- | --- | --- |
| M0 baseline | Build PhoneVR, matching ALVR, and Desktop+; run unmodified stereoscopic stack | ALL THREE BUILDS PASS; actual stereo runtime not tested |
| M1 head pose | ARCore drives both head and stereo views; real 30–50 cm lean visible in SteamVR | NOT IMPLEMENTED |
| M2 hands | Same-camera MediaPipe, two hands, timestamped debug skeleton | GATED ON M1 |
| M3 hand depth | PnP with measured reprojection, metric depth error and calibration | GATED ON M1 |
| M4 unified frames | World fingertips and HMD share calibrated standing origin | NOT IMPLEMENTED |
| M5 panel metadata | Complete versioned Desktop+ snapshots including capture crop/DPI | NOT IMPLEMENTED |
| M6 hover | Accurate plane/UV hover, with no injected clicks | Geometry unit tests only |
| M7 touch | Debounced hysteresis, continuous drag, reliable release and mouse fallback | NOT IMPLEMENTED |
| M8 manipulation | Border grab offset; two-hand scale and rotation | NOT IMPLEMENTED |
| M9 persistence/UX | Named layouts, explicit recenter, calibration and usable settings | NOT IMPLEMENTED |
| M10 optimization | Measured latency, FPS, thermal stability and memory bounds | NOT MEASURED |

## Immediate next engineering work

1. Download the three successful baseline artifacts linked in docs/STATUS.md; all native builds and APK payload/signature checks pass.
2. Run the compiled PhoneVR/ALVR 20.8.0/Desktop+ stack using the actual phone and GPU; record stereo and head-rotation evidence.
3. Record phone model, Android/ROM, ARCore availability, camera exposure when mounted, GPU, Windows version, and network link. No purchase is assumed or required by this checkpoint.
4. Implement ARCore lifecycle and a synchronized native pose snapshot in the existing client. Gate MediaPipe until the real 6-DoF movement test passes.

## Eventual downloadable release

An Android APK plus Windows companion package, pinned upstream dependency setup, privacy-preserving pairing, calibration, and corresponding source/license notices. Release signing must use a stable privately held key; upstream test keystores are not production signing identities. A successful compilation is necessary but does not certify the headset interaction or 14 MVP acceptance tests.

The first hardware checks should be seated or stationary. No passthrough is planned, so a room-scale walking experience is not an initial test requirement.
