# Desktop+ PhoneXR adapter

Implemented source integration for Desktop+ **v3.6**, commit
`031d74d69f08411a9a9b1030d3d428ac02b93549`. It must be built into the
Desktop+ output executable; stock Desktop+ does not provide this interface.

```powershell
python desktopplus-integration/prepare_desktopplus.py path/to/DesktopPlus
```

The checked, idempotent preparation script verifies the upstream commit and source
hashes, adds the adapter compilation unit to `DesktopPlus.vcxproj`, declares the
mutation method, and calls it from `OutputManager::Update` after OpenVR events.
It refuses to overwrite unrelated edits. Build the normal upstream x64 Release
solution with its dependencies. Windows compilation and physical testing are
required; source preparation has been exercised locally, not Windows execution.

## Snapshot contract (version 1)

`%LOCALAPPDATA%\PhoneXR\DesktopPlus\panels.json` is replaced atomically at most
once every 33 ms on Desktop+'s owning thread. The adapter establishes an
inheritable, protected current-user-only directory DACL. No network listener or
OpenVR key suffix parsing is involved. A process-lifetime `sessionId` scopes all
panel IDs and revisions. Handles are opaque IDs; each snapshot resolves its ID
back to the current OverlayManager index. Deleted handles retain revision
tombstones. The bridge must reject stale timestamps and session changes.

| Field | Meaning |
| --- | --- |
| `version` | Integer `1` |
| `sessionId` | Decimal string identifying this adapter instance |
| `sequence`, `updatedUnixMs` | Snapshot counter and UTC epoch milliseconds |
| `ackRequestId`, `ackStatus` | Last processed command acknowledgment |
| `panels` | Complete array, including disabled/noninteractive panels |
| panel `id`, `revision` | Opaque decimal string and integer revision |
| `center`, `right`, `up`, `normal` | Three-element standing-space vectors; meters, right-handed |
| `widthM`, `heightM` | Physical panel dimensions, scale applied once |
| `pixelRect` | `[left,top,width,height]` of the displayed crop in physical screen pixels |
| `crop`, `captureBounds` | Validated capture-local crop and screen capture bounds, same rectangle format |
| `hwnd` | Decimal string; `"0"` for desktop capture |
| `dpi` | Target window DPI; zero for desktop/unsupported targets |
| `visible`, `interactive`, `mutable` | Separate visibility, input eligibility and manipulation eligibility |
| `origin`, `captureSource` | Pinned upstream enum values for diagnostics |

The center uses `GetOverlayMiddleTransform`; physical height uses
`GetOverlayHeight`; crop uses `GetValidatedCropRect`. JSON uses a fixed schema,
locale-independent finite numbers and constant/decimal strings, so arbitrary
window names or raw unescaped strings never enter serialization. Revisions cover
geometry, source, capture mapping, visibility, input permissions, origin, and the
underlying configured transform/offsets. All fields come from the same thread.

## Capture support

- **Desktop Duplication, flat mono:** validated texture crop plus actual DDP
  desktop origin. Individual monitors and combined desktop coordinates work,
  including negative screen origins. HWND is zero; OS input targets the desktop.
- **WinRT window, flat mono:** uses `DWMWA_EXTENDED_FRAME_BOUNDS`, never a naive
  whole-texture-to-client-rectangle mapping. DWM bounds are physical pixels;
  queried window DPI is exported. The window must exist, be visible, not minimized
  or cloaked, and the capture content dimensions must match the DWM frame bounds.
  Resizing mismatches disable input until content dimensions agree. Non-client
  pixels remain non-client pixels, including title bars/borders.
- **WinRT individual monitor:** monitor desktop origin plus validated crop; capture
  content dimensions must match the monitor dimensions.
- **Unsupported for input:** combined WinRT capture, browser/UI/absent sources,
  stereo, curved and theater panels, invalid pose/crop, hidden/transparent panels,
  and captures whose geometry cannot be verified. Exported `interactive=false`
  means their pixel rectangle must not drive input.

Window movement and capture are asynchronous. The snapshot checks current bounds,
but cannot prove which compositor frame the window capture represents. Physical
DPI, resize, title-bar and multi-monitor tests remain necessary. OS touch injection
is desktop-coordinate input and does not promise background delivery.

## Manipulation command

The bridge writes a unique temporary file in the same directory, closes it, then
atomically replaces `command.bin`. It must allow only one outstanding request.
The adapter atomically claims the file before reading and accepts only **108
bytes**, little endian, equivalent to Python:

```python
struct.pack('<4sIQQQQ16ff', b'PXR1', 1, int(session_id), int(panel_id),
            revision, request_id, *row_major_world_matrix_4x4, width_m)
```

A command must be modified within the last 500 ms, match session and revision,
refer to a mutable panel, contain a finite proper rigid matrix within 100 m, and
have width in `[0.10,10.0]` meters. Invalid matrices, reflection/scale, missing
panels, stale geometry and active Desktop+ dragging are rejected. `ackStatus` is
`accepted`, `stale`, `invalid`, or `unavailable` (`none` before any request).
Unreadable/malformed packets may lack a trustworthy request ID; the bridge must
time out instead of waiting indefinitely for acknowledgment.

**Room and seated origins only** are mutable. The adapter uses the same
`GetBaseOffsetMatrix` inverse and removal of local configuration offsets as
`OverlayDragger::DragFinish`, sets configured pose and width together, and calls
`ApplySettingTransform` on the owning thread while restoring the previous
current-overlay selection. Existing Desktop+ configuration persistence saves the
result on its normal save path. Dashboard, HMD/hand/tracker-following and theater
origin mutations are deliberately disabled because their extra anchoring,
smoothing or docking behavior needs a separately verified conversion.

## License

Adapter source and preparation script: **GPL-3.0-or-later**. Desktop+ upstream is
GPL-3.0; retain its LICENSE and attribution when building or distributing a fork.
Distribute the corresponding source for the exact fork, these adapter files and
preparation/build instructions alongside any derivative binary, and retain
upstream dependency notices. This directory adds original integration code and
uses upstream public C++ types and implementation hooks; it is not a standalone
binary plug-in for an unmodified Desktop+ executable.
