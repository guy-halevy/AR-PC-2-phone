# PhoneXR development setup

Use matching PhoneXR Android and Windows builds with protocol v2; the earlier v1 packages cannot exchange hand packets. This procedure has not yet been completed on physical hardware.

1. Install SteamVR through Steam on the Windows PC. Download the PhoneXR Windows artifact ZIP and run `installer-dist/PhoneXR-Companion-Setup.exe`. The per-user installer bundles patched Desktop+, the matching ALVR streamer, the hand bridge, the companion UI, and corresponding source/notices.
2. Open **PhoneXR Companion** from the Start menu. Use **ALVR** to open the streamer dashboard and complete its SteamVR driver setup, then use **Desktop+** to create your panels. These programs run in your normal desktop session.
3. Select the PC's private IPv4 address and click **Start connection**. Copy the pairing code for the phone. Hand input starts disabled; the companion has explicit **Enable hand input**, **Disable and release**, and **Stop** controls.
4. Download and extract the Android artifact ZIP and install the top-level `PhoneXR.apk`. It is a development APK with application ID `org.phonexr.client`. Separately built debug APKs may have different signing keys. Choose ALVR, complete Cardboard viewer setup, and accept the phone in the PC's ALVR dashboard.
5. In **PhoneXR setup**, enter the pairing code. Enable AR and hand tracking, grant camera permission, and complete the Google Play Services for AR prompt if shown. Set eye height and mounted camera-to-eye offset, then recenter while facing the intended forward direction. The stereo hand-skeleton display is enabled by default and can be toggled here.
6. Verify the image and head movement, then enable input in the companion and assess a test panel. Index contact provides touch/drag; border pinches translate unlocked panels, and two pinches scale/rotate them. Lost or stale hands release touch and hide their skeleton. Keep a physical mouse/keyboard available for initial validation.

Pair again after restarting the Windows bridge. If app data is cleared, restart the bridge to create a fresh session. Do not share the pairing URI or place it in logs/screenshots. The sender processes images locally and sends derived coordinates only.

## Physical acceptance still required

Record phone/Android version, PC GPU/driver, headset, refresh rate and network. Check left/right eye ordering, optics, stable world position under translation and rotation, pause/resume and recenter. Measure fingertip depth/contact error and latency, including occlusion and tracking loss. Exercise panel crop, multiple-monitor origins, DPI changes, window closure, failed touch updates and app shutdown. Run a sustained thermal/session test.

A CI green check cannot establish any of those physical results. The software includes a stereo hand-skeleton overlay and per-user PC installer. Automatic metric calibration and physical hardware validation remain open. SteamVR setup and phone pairing still require user interaction.
