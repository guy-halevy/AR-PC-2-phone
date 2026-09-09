# PhoneXR development setup

Use matching PhoneXR Android and Windows builds with protocol v2; the earlier v1 packages cannot exchange hand packets. This procedure has not yet been completed on physical hardware.

1. On the PC, install SteamVR and extract the matching ALVR 20.8.0 streamer package linked in STATUS.md. Start its dashboard and follow its driver setup. Keep the desktop session unlocked.
2. Extract the PhoneXR Windows package. Run its patched Desktop+ executable with SteamVR and create a flat desktop/window panel. The bridge reads the current panel snapshot automatically.
3. Run `PhoneXRBridge.exe --host YOUR_PC_LAN_IPV4` using the PC's private-network IPv4 address. The console prints a private pairing URI. Input stays disabled until you press E; D releases/disables it and Q releases/quits.
4. Install the APK from the matching PhoneXR Android artifact. The development APK is debug signed; separately built packages may have different signing keys. Choose the ALVR client path and complete Cardboard viewer setup. Connect the phone to the PC's network and accept it in the ALVR dashboard.
5. In the PhoneXR setup controls, enter the bridge pairing URI. Enable AR and hands, grant camera permission, and complete the ARCore installation prompt if shown. Set eye height and the mounted camera-to-eye offset; recenter while facing the intended standing-space forward direction.
6. Verify stereo and head movement first, then enable Windows input with E and assess contact against a test panel. Loss of hands/tracking should release contact. Border pinches translate unlocked panels; two pinches scale and rotate in the panel plane.

Pair again after restarting the Windows bridge. If app data is cleared, restart the bridge to create a fresh session. Do not share the pairing URI or place it in logs/screenshots. The sender processes images locally and sends derived coordinates only.

## Physical acceptance still required

Record phone/Android version, PC GPU/driver, headset, refresh rate and network. Check left/right eye ordering, optics, stable world position under translation and rotation, pause/resume and recenter. Measure fingertip depth/contact error and latency, including occlusion and tracking loss. Exercise panel crop, multiple-monitor origins, DPI changes, window closure, failed touch updates and app shutdown. Run a sustained thermal/session test.

A CI green check cannot establish any of those physical results. The present release does not include a hand-skeleton overlay, automatic metric calibration, or a one-click PC installer.
