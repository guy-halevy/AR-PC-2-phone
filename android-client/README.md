# Android integration status

No PhoneXR Android client is implemented or packaged in this checkpoint.

Extend the pinned PhoneVR sources after the unmodified build/runtime gate passes. Source hooks and frame/timing requirements are in [ARCHITECTURE.md](../ARCHITECTURE.md). Preserve ALVR decoding/Cardboard optics, replace both HMD and stereo-view pose paths, and remove upstream analytics before claiming local-only processing.

The diagnostic Python replay is not an Android implementation. Do not rename its source archive to `.apk` or use an unrelated upstream APK as a PhoneXR release.
