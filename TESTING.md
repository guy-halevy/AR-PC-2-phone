# Test evidence

Verified locally on Linux with g++ 13.3.0 and Python. Reproduce using `python tools/run_checks.py`.

| Check | Observed result | What it establishes |
| --- | --- | --- |
| C++17 compilation | PASS with `-Wall -Wextra -Werror -pedantic` | Shared math compiles on this Linux toolchain |
| Coordinate/UV tests | PASS, 339 deterministic checks | Numerical composition, inverse, calibration, camera axes, transformed/scaled corners, invalid input |
| Python tests | PASS, 15 tests | Protocol validation, HMAC tampering, session/sequence/timestamp rules, expiry, and replay |
| Loopback network cases | PASS | Real local UDP receipt, synthetic motion and pause, watchdog amid invalid traffic |
| Windows protocol suite | PASS, 15 tests on windows-2022 | [CI run](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762726); includes the injected oversized-error regression |
| PhoneVR Android build | BLOCKED | Local Gradle reaches configuration, then cannot resolve Spotless 6.20.0 |
| ALVR build | BLOCKED | `cargo` absent |
| Desktop+ v3.6 Release x64 | PASS on windows-2022 | [CI build and source artifact](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762666); no desktop runtime test |
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

There is no clock sync, no delivered hand protocol, and no Windows input release state machine. Their absence is documented rather than substituted with synthetic test results.
