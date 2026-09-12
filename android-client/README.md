# Android PhoneXR development client

`scripts/prepare_phonexr.py` applies checked hooks to the baseline-prepared, pinned PhoneVR checkout and copies this directory's Java/native implementation and instrumentation tests. CI builds a real `org.phonexr.client` arm64 APK.

`XrController` owns ARCore lifecycle, camera intrinsics and standing-space calibration. `HandTracker` runs local MediaPipe inference; `HandPoseEstimator` uses OpenCV PnP. `HandSender` sends authenticated derived landmarks, and `PairingStore` encrypts pairing material using Android KeyStore. `phonexr_pose.hpp` synchronizes head snapshots and preserves capture timestamps in ALVR.

The derivative removes Firebase dependencies/plugin and disables upstream crash-reporter initialization and app backup. It retains PhoneVR's native streaming and Cardboard optics. Camera-to-eye calibration, metric hand accuracy, thermal performance and physical stereo remain unverified. A stereo hand-skeleton overlay uses the matching ALVR per-eye view and hides stale observations. Automatic metric calibration remains unimplemented.

The `test-app` component fixture uses production Java sources on API30 x86, an ABI shipped by MediaPipe 0.10.14. It does not exercise the native ALVR/ARCore headset runtime. The integration workflow runs the five `XrInstrumentationTest` methods, including an EGL/GLES3 renderer probe with failure propagation enabled. Upstream ALVR screenshot tests requiring a separate streaming setup are outside this component suite. See [status](../docs/STATUS.md) and [setup](../docs/DEVELOPMENT_SETUP.md).
