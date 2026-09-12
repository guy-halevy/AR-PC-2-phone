# Roadmap and acceptance

The user revised the milestone order: implement AR and hands first, then perform physical stereo testing. Source completion and physical acceptance are recorded separately.

| Area | Development implementation | Physical acceptance |
| --- | --- | --- |
| Streaming baseline | PhoneVR + matching ALVR 20.8.0 + Desktop+ builds | Pending |
| Head pose | ARCore lifecycle, anchor/recenter, head + stereo-view integration | Pending translation, rotation, drift and loss tests |
| Hands and depth | Same-camera MediaPipe, OpenCV PnP, timestamp and geometry gates | Pending metric accuracy and occlusion tests |
| Unified coordinates | Shared standing frame for head and hand landmarks | Pending calibration validation |
| Panel adapter | Native snapshots with validated capture mapping and revision-checked commands | Pending real DPI/crop/window tests |
| Hover and touch | Projection, contact debounce/hysteresis, one-contact touch and release | Pending physical input; visual hover cursor not completed |
| Manipulation | Border grab, two-hand scale and in-plane rotation | Pending physical gesture tests |
| Setup and persistence | Android settings/pairing/recenter; Desktop+ retains its layout system | Consumer setup flow and repeatable physical origin restoration pending |
| Debug visualization | Stereo skeleton rendered into matching eye views before Cardboard distortion | Implemented; GPU and physical validation tracked in STATUS.md |
| Performance | Bounded hand inference and transport queues | FPS, latency, thermal behavior and memory not measured |

Development binaries and source are linked in docs/STATUS.md. Release signing with a stable private key, all 14 physical product acceptance checks remain open. A per-user Windows installer is implemented. The current build does not establish a walking/passthrough experience.
