# PhoneXR Windows bridge

The bridge receives authenticated PhoneXR hand landmarks, maps index contact to the live Desktop+ panel snapshot, and injects one Windows touch contact. `--mouse-fallback` explicitly selects single-pointer mouse compatibility. Border thumb/index pinches translate an unlocked panel; two pinches scale and rotate it in its plane. Commands carry session, panel and revision identifiers, and wait for Desktop+ acknowledgement.

Run the patched Desktop+ development build in your normal Windows 10/11 desktop session with SteamVR. Then run:

```powershell
PhoneXRBridge.exe --host 192.168.1.10
```

Replace the address with this PC's LAN IPv4 address. For a source checkout, install `requirements.txt`, then run `python bridge.py --host 192.168.1.10` from this directory. The console prints a session-specific pairing URI. Keep it private and enter it in the PhoneXR Android pairing screen. Restarting the bridge rotates its key. Input starts disabled: press **E** to enable, **D** to disable and release, or **Q** to release and quit.

The default snapshot is `%LOCALAPPDATA%\PhoneXR\DesktopPlus\panels.json`. Missing or stale snapshots, capture changes, tracking loss, confidence loss and stale frames release contact. Unsupported or unavailable captures are excluded. Only flat, visible, correctly mapped panels accept input; manipulation additionally requires an unlocked room/seated panel. Elevated windows and secure desktops may reject Windows input.

`--max-reprojection-px` sets the calibration quality gate from 0.1 to 8 pixels (default 8). `--port` defaults to UDP 39571; use the same port in pairing. If Windows asks about network access, scope it to the private network used by the phone.

The `Windows PhoneXR adapter and bridge` workflow compiles the patched Desktop+ and packages `PhoneXRBridge.exe`, with corresponding source and dependency notices. Its portable regressions and `--help` smoke test do not inject physical input. Real SteamVR, window/DPI/crop mapping, touch behavior and tracking still require the hardware acceptance checklist; a successful CI build alone does not validate them.
