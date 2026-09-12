# Test evidence

Verified locally on Linux with g++ 13.3.0 and Python. Reproduce using `python tools/run_checks.py`.

| Check | Observed result | What it establishes |
| --- | --- | --- |
| C++17 compilation | PASS with `-Wall -Wextra -Werror -pedantic` | Shared math compiles on this Linux toolchain |
| Coordinate/UV tests | PASS, 339 deterministic checks | Numerical composition, inverse, calibration, camera axes, transformed/scaled corners, invalid input |
| Python tests | PASS, 15 tests | Protocol validation, HMAC tampering, session/sequence/timestamp rules, expiry, and replay |
| Loopback network cases | PASS | Real local UDP receipt, synthetic motion and pause, watchdog amid invalid traffic |
| Windows protocol suite | PASS, 15 tests on windows-2022 | [CI run](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762726); includes the injected oversized-error regression |
| PhoneXR arm64 APK | PASS | [Run 34365142203](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142203): corrected OpenCV loader; APK signature, all six required native libraries and exact model hash verified; no physical runtime test |
| PhoneVR Android APK | PASS | [CI run](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34195739292): Cardboard, ALVR native client, APK assembly, native payload and signature verification |
| ALVR Windows native build | PASS | [CI run](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34195828548): streamer/dashboard compilation and source packaging |
| Desktop+ v3.6 Release x64 | PASS on windows-2022 | [CI build and source artifact](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762666); no desktop runtime test |
| Android emulator startup | PASS on API34 x86_64 | [Run 34230007065](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34230007065): installs, shows launcher, opens native ALVR activity and reaches Cardboard viewer setup without a detected crash; explicit foreground assertion and app-process crash checks passed |
| Android hand components | PASS, five tests on API30 x86 | [Run 34365142111](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34704809509): real MediaPipe model load/blank frame, OpenCV known-geometry PnP, AES-GCM/KeyStore/sequence persistence and frame timing and actual stereo GLES3 rendering; all five JUnit results required; component fixture uses production Java, not full headset runtime |
| Windows interaction and hand protocol | PASS, 28 tests | [Run 34704809482](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34704809482): contact loss/release, geometry/mutation, authenticated packets and port recreation; no physical injection |
| Native AR snapshot | PASS | Actual production header with narrow JNI/Cardboard doubles checks timestamp/freshness, frozen pose, invalid-pose rejection and recovery |
| External second opinion | UNAVAILABLE | Both `codex` and `agy` commands absent; no external review completed |

Native build progress after the local audit is tracked in [STATUS.md](docs/STATUS.md). SteamVR, mounted-phone camera, and actual device tests remain unrun.

## Product acceptance — all pending

| Brief test | Required real evidence | Status |
| --- | --- | --- |
| 1 HMD | Correct stereoscopic stream and head rotation | NOT RUN |
| 2 Positional tracking | 30–50 cm head translation reaches SteamVR | NOT RUN |
| 3 World panel | Panel stays in calibrated world space during head motion | NOT RUN |
| 4 Hand visualization | Two-hand skeleton from mounted phone camera | NOT RUN |
| 5 3D fingertip | Stable, correctly directed metric depth | NOT RUN |
| 6 Hover | Finger-to-panel cursor follows correctly | NOT RUN |
| 7 Ratio mapping | Nine real touch targets, average error <=5% per axis | NOT RUN; geometry unit tests are not this test |
| 8 Click | Windows control activates once | NOT RUN |
| 9 Drag | Continuous touch down/update/up stream | NOT RUN |
| 10 Move | Border grab preserves offset and released position | NOT RUN |
| 11 Scale | Smooth two-hand scale with limits | NOT RUN |
| 12 Rotate | Predictable two-hand rotation | NOT RUN |
| 13 Four panels | Four simultaneous independent interactive captures | NOT RUN |
| 14 Persistence | Saved layout restores relative to re-established origin | NOT RUN |

## Additional release gates

Measure actual camera/inference/streaming rate, hand depth error, latency percentiles, tracking loss recovery, battery/temperature behavior and memory usage. Test rotated phone mounting, varied hand visibility, display DPI/crop changes, multiple monitors, occluded/elevated target windows, and display disconnects. A normal protected-content black capture must be reported as unsupported; no protection bypass is part of this design.

## Regressions already checked

One byte of an authenticated packet is altered at each of its 100 positions; every modification is rejected. Duplicate, reordered and old timestamp packets cannot update current tracking state. Sequence rollover is accepted only within the forward half of uint32 space. Invalid packet floods do not reset the watchdog. Fresh session material prevents an old session being mistaken for a new connection, provided the documented fresh-pairing requirement is followed.

The v2 hand protocol and Windows release state machine are implemented. Their 23 interaction/transport regressions pass locally; native snapshot timing/loss regressions also pass. There is no independent clock synchronization, and physical input remains untested. The Android component suite and current native build evidence are tracked in STATUS.md. An earlier integration run ignored a failed upstream test; it must not be treated as an all-tests-pass result (see REVIEW.md).
