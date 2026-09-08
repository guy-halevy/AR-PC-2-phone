# License and dependency notices

The root MIT license applies to the original PhoneXR Python/C++ code, tests, and original documentation in this checkpoint. It does not relicense upstream projects, model files, platform services.

| Component | Source license / status | Distribution decision |
| --- | --- | --- |
| Original PhoneXR portable modules | MIT, root LICENSE | Included as source |
| PhoneVR | [GPL v3 license](https://github.com/PhoneVR-Developers/PhoneVR/blob/7fdcebee4a662eb8a1c7a8b19774aac71820a772/LICENSE) | Source fetched for audit, not bundled; any derivative must retain compatible licensing/source obligations |
| ALVR | [MIT](https://github.com/alvr-org/ALVR/blob/1d121fa7e0761ef26473c6b3f3fbd9b6051ce033/LICENSE) | Referenced, not bundled |
| Desktop+ | [GPL v3](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/LICENSE) | Referenced, not bundled; future fork remains GPL-compatible |
| ARCore | [SDK license](https://github.com/google-ar/arcore-android-sdk/blob/master/LICENSE); runtime terms are separate | No SDK/runtime binary bundled |
| MediaPipe | [Apache 2.0 source license](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE) | No library/model bundled; verify chosen model artifact notices before release |
| OpenCV | [Apache 2.0 source license](https://github.com/opencv/opencv/blob/5.0.0/LICENSE) | No library bundled |

SteamVR, Windows, Android services and future third-party packages keep their respective terms. This checkpoint does not claim that every required component is open source or universally compatible. No DRM circumvention or protected-video bypass is included.

Before a binary release, collect exact dependency/model versions, notices, corresponding source where required, and signing metadata. No APK or EXE is being distributed here.
