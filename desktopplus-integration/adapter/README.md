# Proposed Desktop+ adapter — no adapter implemented yet

Baseline: [Desktop+ v3.6](https://github.com/elvissteinjr/DesktopPlus/releases/tag/v3.6), commit `031d74d69f08411a9a9b1030d3d428ac02b93549`. Reuse its GPL-compatible source and owning-thread mutation mechanisms.

| Requirement | Source hook | Implementation constraint |
| --- | --- | --- |
| Enumerate current panels | `src/Shared/OverlayManager.h/.cpp`: `GetOverlayCount`, `GetOverlay`, `GetConfigData` | OpenVR key suffix is not a reliable current overlay index |
| Effective standing pose | `GetOverlayMiddleTransform` | Account for crop/aspect and origin modes |
| Persistent configured pose | `OverlayConfigData::ConfigTransform` | Origin-relative, not automatically world-space |
| Apply pose and physical width | `OutputManager::ApplySettingTransform` | Apply configuration then let Desktop+ update OpenVR |
| World-to-config conversion | `OverlayDragger::DragFinish` | Invert origin base and remove additional offsets |
| Physical height | `OutputManager::GetOverlayHeight` | Derive from validated crop/stereo mode |
| Exact crop | `Overlay::GetValidatedCropRect` | Raw user crop values may have defaults/invalid extents |
| Window capture identity | `configid_handle_overlay_state_winrt_hwnd` | Include capture mode; a desktop source is different |
| Captured content dimensions | `configid_int_overlay_state_content_width/height` | Refresh on resize/capture changes |

Source references: [OverlayManager](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/OverlayManager.cpp), [configuration](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/ConfigManager.h), [OutputManager](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/DesktopPlus/OutputManager.cpp), [drag conversion](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/OverlayDragger.cpp), [crop handling](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/DesktopPlus/Overlays.cpp).

Existing Win32 messages expect matching dashboard/UI builds and do not establish a versioned public API. Some transform state is transmitted as separate float updates, without a verified arbitrary-sidecar matrix assembly/apply path. [IPC contract](https://github.com/elvissteinjr/DesktopPlus/blob/v3.6/src/Shared/InterprocessMessaging.h).

Design a local bridge with a schema version, request IDs, full atomic panel snapshots, per-panel revision numbers, and user-session access control. Reject stale mutations and apply accepted updates on the dashboard's owning thread. Export the actual crop-to-desktop mapping alongside the standing transform; do not let geometry and capture metadata come from different revisions. This is a proposed interface, not an existing endpoint.

A Desktop+ fork remains subject to its GPL license. Do not distribute an executable adapter that depends on unimplemented hooks.
