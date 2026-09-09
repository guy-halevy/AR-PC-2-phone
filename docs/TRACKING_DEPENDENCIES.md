# Tracking dependencies and evidence

Research checked 2026-09-08. Recommendation: MediaPipe Tasks Hand Landmarker for phone RGB hand observations, OpenCV for calibrated pose estimation, and ARCore for the phone's world pose. This is an engineering baseline, not a security certification or a claim of measured device reliability.

## Selected baseline

| Component | Pin | Purpose and evidence |
|---|---|---|
| MediaPipe Tasks Vision | `com.google.mediapipe:tasks-vision:0.10.14` | Android Hand Landmarker; official AAR manifest declares min SDK 24, target 30. No AAR minimum-compile metadata found. |
| OpenCV | `org.opencv:opencv:4.10.0` | Java `Calib3d.solvePnP`/`projectPoints`; official AAR declares min SDK 21, target 31, minimum compile SDK 1. |
| ARCore | `com.google.ar:core:1.46.0` | Camera intrinsics and phone world pose; AAR declares min SDK 21, target 35. No AAR minimum-compile metadata found. AR operation still requires a supported device and runtime. |
| Guava override | `com.google.guava:guava:32.1.3-android` | Replace MediaPipe's old transitive `27.0.1-android`; addresses the advisory below. Check the resolved graph. |

The three AAR manifests and OpenCV metadata were downloaded directly and inspected during this review. They show no direct minimum-compile conflict with this project's compile SDK 34 / min SDK 26 / JDK 17 baseline. An AAR's target SDK is not its minimum compile SDK. This does **not** establish that the complete transitive dependency graph builds, that native libraries meet all contemporary distribution requirements, or that newer releases cannot be used. Keep exact pins; upgrade deliberately with a build and phone test. These are compatibility baseline versions, not asserted latest releases.

Primary artifact metadata: [MediaPipe POM](https://dl.google.com/dl/android/maven2/com/google/mediapipe/tasks-vision/0.10.14/tasks-vision-0.10.14.pom), [MediaPipe AAR](https://dl.google.com/dl/android/maven2/com/google/mediapipe/tasks-vision/0.10.14/tasks-vision-0.10.14.aar), [OpenCV AAR](https://repo.maven.apache.org/maven2/org/opencv/opencv/4.10.0/opencv-4.10.0.aar), [ARCore POM](https://dl.google.com/dl/android/maven2/com/google/ar/core/1.46.0/core-1.46.0.pom), [ARCore AAR](https://dl.google.com/dl/android/maven2/com/google/ar/core/1.46.0/core-1.46.0.aar).

## Model and licenses

Use the official float16 version-1 bundle containing palm detection and hand landmark models: [hand_landmarker.task](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task). The acquisition recorded in this work produced 7,819,105 bytes and SHA-256:

```text
fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1
```

MediaPipe code and its Android artifact are Apache-2.0 licensed; the model card independently identifies Apache-2.0 for the hand model. The documentation footer's sample-code license alone would not establish the model license. Keep applicable license and third-party notices with distributions. [MediaPipe license](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE), [official model card, page 2](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf).

OpenCV 4.5.0 and later use Apache-2.0. ARCore's AAR/POM instead specify Google's ARCore Additional Terms, including end-user notices. Therefore the hand detector is free open-source software with a permissively licensed model, but the complete ARCore-based system is not entirely open source. Local hand inference does not require a paid inference service. [OpenCV license](https://opencv.org/license/), [ARCore terms](https://developers.google.com/ar/develop/terms).

## Alternatives

| Choice | Assessment for this phone pipeline |
|---|---|
| MediaPipe Hand Landmarker | Best fit: supported Android task, single RGB input, landmarks and handedness. On-device processing avoids sending camera frames to a cloud inference service. |
| Monado Mercury | Strong candidate for a separate calibrated stereo-headset implementation. Current integration documentation lists Index, Luxonis stereo, WMR and Rift S, with exposure caveats. It is not a drop-in monocular Android task and adds ONNX Runtime plus OpenCV integration. Monado's source license is Boost Software License; a future integration must also inventory its models and dependencies. |
| OpenCV alone | Supplies geometry, calibration and inference building blocks, not a complete comparable hand-tracking solution. PnP still needs reliable 2D/3D correspondences and camera calibration. |
| Direct model inference with another runtime | Could reuse a permissive model, but requires implementing detection, crops, temporal association and coordinate conversion currently supplied by MediaPipe. More engineering and validation for no established gain here. |

Sources: [MediaPipe task](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker), [Mercury hardware and build requirements](https://monado.freedesktop.org/handtracking/), [Monado source license](https://gitlab.freedesktop.org/monado/monado/-/raw/main/LICENSE), [OpenCV PnP documentation](https://docs.opencv.org/4.10.0/d5/d1f/calib3d_solvePnP.html). Comparative suitability is this project's engineering assessment.

## Security findings and limits

MediaPipe's public GitHub advisory page showed no published advisories when checked. OpenCV's public repository-advisories API returned an empty array; its security policy provides a private reporting channel. Neither result proves absence of vulnerabilities, including embedded native components. [MediaPipe advisories](https://github.com/google-ai-edge/mediapipe/security/advisories), [OpenCV advisory API](https://api.github.com/repos/opencv/opencv/security-advisories), [OpenCV security policy](https://github.com/opencv/opencv/security).

There is a concrete transitive issue: MediaPipe 0.10.14's POM requests Guava 27.0.1-android. That falls within the affected range of CVE-2023-2976 / GHSA-7g45-4rm6-3mm3, concerning temporary-file handling in `FileBackedOutputStream`. The advisory identifies 32.0.0-android as patched and recommends at least 32.0.1 because of a regression in 32.0.0. The proposed 32.1.3-android override clears that range. This is a dependency finding, not evidence that the phone's tracking path exposes the vulnerable operation. [Advisory and affected versions](https://github.com/advisories/GHSA-7g45-4rm6-3mm3).

Before release, resolve and lock the full dependency graph, verify checksums, inventory bundled native components and licenses, and scan exact resolved versions. Test model corruption handling, camera lifecycle, bounded inference queues, resource cleanup and stale-result rejection. No full binary audit, malware analysis, exhaustive CVE audit or hardware reliability certification was performed in this dependency review.

## Tracking correctness gates

MediaPipe world landmarks are hand-relative estimates, not ARCore world positions. PnP gives an estimated object-to-camera transform; the calibrated camera pose at the observation timestamp is then required to place that hand in the AR scene. Model scale and occlusion can still make depth inaccurate. Reject non-finite, behind-camera, stale or high-reprojection-error results. The model card identifies occlusion and difficult camera conditions as limitations; empirical phone testing remains necessary.

For handedness, Tasks 0.10.14 explicitly maps classifier index 0 to Right and 1 to Left, opposite the legacy Hands label file. Preserve Tasks category names for unmirrored rear-camera input rather than importing legacy selfie-swap advice. This source-based choice still requires a physical left/right test with the final image-rotation path. [Tasks graph](https://github.com/google-ai-edge/mediapipe/blob/v0.10.14/mediapipe/tasks/cc/vision/hand_landmarker/hand_landmarks_detector_graph.cc), [legacy label file](https://github.com/google-ai-edge/mediapipe/blob/v0.10.14/mediapipe/modules/hand_landmark/handedness.txt).

Measure inference latency, dropped frames, thermal behavior, pose stability, hand identity across crossings, and loss/reacquisition on the intended phones. Test palm-facing and back-of-hand poses, varying illumination, image rotation, two hands, occlusion and ARCore tracking loss. Vendor benchmark numbers are not measurements of this integrated pipeline.

## Subsequent implementation evidence

The pinned ARCore, MediaPipe and OpenCV combination compiled into the actual PhoneXR Android derivative in [run 34314584325](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34314584325). This supersedes the earlier uncertainty about whether the selected graph can build together. It does not replace a full dependency lock/inventory or hardware accuracy testing. The current strict model/geometry instrumentation result is tracked in STATUS.md; an earlier mixed upstream test run suppressed a failure and is excluded from all-tests-pass claims.
