# Architecture

Updated: 2026-09-09. Target: Android + Windows. AR, hand and panel-input development implementations exist; physical acceptance remains pending. See docs/STATUS.md for observed evidence.

## Reuse decisions

Keep the PhoneVR client and its ALVR `20.8.0` protocol baseline. PhoneVR's latest release explicitly names that pairing; inspected master also pins the corresponding ALVR commit. Do not substitute ALVR `20.14.1` without a compatibility test. [PhoneVR release](https://github.com/PhoneVR-Developers/PhoneVR/releases/tag/v2.0.0-beta).

Add ARCore session ownership at the Android rendering lifecycle, publish an immutable synchronized pose snapshot to native code, and replace the Cardboard-only head pose. Both the head-device motion and stereo view poses must use the same transform and timing. The existing ALVR C API already accepts positional motion; no new streaming protocol is proposed. [Native PhoneVR source](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/code/mobile/android/PhoneVR/app/src/main/cpp/alvr_main.cpp), [matching ALVR interface](https://github.com/alvr-org/ALVR/blob/1d121fa7e0761ef26473c6b3f3fbd9b6051ce033/alvr/client_core/src/c_api.rs).

The existing streaming HMD remains the pose owner. An unrelated overlay process cannot submit an HMD pose through the ordinary client API, and adding a second HMD driver does not replace the active HMD. [OpenVR driver contract](https://github.com/ValveSoftware/openvr/blob/v2.15.6/docs/Driver_API_Documentation.md).

Fork Desktop+ at `v3.6` for a narrow versioned bridge. Its existing dashboard/UI messages are private implementation details, not a verified complete sidecar API. See [adapter design](desktopplus-integration/adapter/README.md).

## Frames and units

All spatial lengths use meters. All internal orientations use unit Hamilton quaternions, serialized `x,y,z,w`. Column-vector convention: `T_B_A` maps coordinates from A into B. `T_C_B * T_B_A` applies the right transform first. Pose transforms are rigid; panel scale is a separate positive value.

| Frame | Axes / meaning |
| --- | --- |
| AR world | ARCore's right-handed session world; numerical coordinates can adjust |
| Physical AR/OpenGL camera | +X right, +Y up, -Z viewing direction; based on image readout |
| OpenCV camera | +X right, +Y down, +Z viewing direction |
| SteamVR standing space | Right-handed, meters; +Y up; origin must be calibrated |
| HMD | Head/eye reference, distinct from the rear camera center |
| Panel local | Center origin; +X right, +Y up, +Z front normal; plane Z=0 |
| Panel UV | Top-left (0,0), bottom-right (1,1) |

The camera basis conversion is `diag(1,-1,-1)`, a proper 180-degree rotation about X. It is not a reflection. Physical-camera pose differs from display-oriented pose by a display rotation; do not use a screen-rotated image with unmodified CPU-camera intrinsics. [ARCore Camera](https://developers.google.com/ar/reference/java/com/google/ar/core/Camera), [OpenCV PnP conventions](https://docs.opencv.org/4.13.0/d5/d1f/calib3d_solvePnP.html).

## Origin handling

Use a session anchor and an explicit calibrated standing-space placement:

```text
T_steam_ar(t)  = T_steam_anchor * inverse(T_ar_anchor(t))
T_steam_hmd(t) = T_steam_ar(t) * T_ar_camera(t) * T_camera_hmd
```

`T_camera_hmd` includes camera-to-eye offset and mounted-phone orientation. It must be supplied, not silently assumed to be identity. The shared C++ module implements this composition with explicit inputs.

This is an engineering design based on ARCore's updating anchor poses. It does not guarantee drift-free tracking. Filter small corrections separately from head motion; never smooth away deliberate head movement. Local anchors do not automatically restore a physical origin after app restart. Saved layouts require a repeatable recenter/calibration step before becoming world-aligned again. [ARCore anchors](https://developers.google.com/ar/develop/anchors).

The brief's repeated `T_steam_hmd * inverse(T_ar_hmd)` cannot independently correct alignment if the SteamVR HMD was itself generated from ARCore. It reconstructs the existing mapping and can add time mismatch. Use independent calibration or a genuinely independent reference.

## Timing and tracking loss

ARCore capture time and PhoneVR's ALVR target clock must be mapped explicitly. ARCore does not promise the same time base as `CLOCK_BOOTTIME`. Do not label an old camera pose as freshly predicted. Retain capture time, processing age, and receive time separately. [ARCore Frame](https://developers.google.com/ar/reference/java/com/google/ar/core/Frame).

The shipped diagnostic receiver only validates sender timestamp progression and sender processing age, then uses its own clock for a 150 ms liveness timeout. It cannot measure one-way latency or reject every delayed first packet. It must not drive input or HMD prediction without clock/session integration.

The inspected ALVR C pose structure has no invented tracking-valid flag. Gate unavailable poses and verify actual driver timeout behavior. Any future touch/manipulation component must release contacts on pause, missing hands, socket loss, window disappearance, and shutdown.

## Hands — development implementation

Acquire images from ARCore rather than opening a competing camera owner. Close each image, retain matching pose/intrinsics/timestamp, and use bounded asynchronous inference. MediaPipe returns image landmarks, handedness, and hand-centered 3D geometry; that geometry is not AR world position. [ARCore ML integration](https://developers.google.com/ar/develop/java/machine-learning), [MediaPipe Android guide](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/android).

The implemented pipeline estimates camera-relative hand pose with PnP, reject poor reprojection or negative-depth solutions, and assess personalized scale with real recordings. Reprojection agreement alone does not prove metric depth accuracy. The PnP implementation remains experimental until measured on real hands. Direct fingertip contact remains the primary target; alternative gestures may supplement it only after measurement.

## Panel input

Transform world fingertip to panel local, apply physical dimensions and scale once, then compute `u=x/width+0.5`, `v=0.5-y/height`. Reject out-of-bounds/behind-panel approach before contact logic; clamp only valid edges. The Windows ContactEngine adds debounce, depth hysteresis and tracking-loss release to this geometry.

Map UV through the actual validated capture crop and desktop pixel origin. Desktop+ window textures may include non-client frame content, so blindly mapping the whole panel to `GetClientRect` is wrong. Preserve crop, DWM capture bounds, client-in-capture bounds, monitor origin and DPI context. [Desktop+ input mapping](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/DesktopPlus/OutputManager.cpp).

Implemented Windows input uses checked `InitializeTouchInjection`/`InjectTouchInput` calls and stable IDs. UP uses the preceding successful UPDATE's location; retryable failures must not advance logical state. Input is desktop-coordinate input, not guaranteed background-window delivery. Mouse fallback respects normal OS boundaries. [Touch injection](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-injecttouchinput), [SendInput restrictions](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput).

## Privacy and interaction design

The new tracking pipeline processes camera frames locally, without recording or raw-frame transmission. The derivative preparation removes upstream Firebase dependencies and disables crash-reporter initialization. Keep tracking and error states visible.

Apple Design principles guide the planned UX: immediate feedback, direct manipulation preserving grab offset, distinct panel borders for layout editing, system typography, accessible control sizes, and reduced motion. The VR world must remain stable rather than animate with UI decoration. A basic Android settings/status interface is implemented; visual hand feedback and a complete consumer setup flow remain pending.
