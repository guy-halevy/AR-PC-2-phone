# Diagnostic pose packet v1

This is the implemented preparation protocol, not the future complete HMD/hand protocol. It carries physical-camera pose in AR world, never a calibrated SteamVR pose.

All integers and floats are little-endian. Body is Python struct `<4sBBHIQ16s7fI`; the appended tag is HMAC-SHA256 over all body bytes using a fresh 32-byte key.

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 4 | ASCII PXRP |
| 4 | 1 | Version = 1 |
| 5 | 1 | State: 0 paused, 1 tracking |
| 6 | 2 | Reserved = 0 |
| 8 | 4 | Sequence uint32 |
| 12 | 8 | Sender monotonic capture timestamp in ns |
| 20 | 16 | Random pairing session ID |
| 36 | 12 | Camera translation XYZ float32, meters |
| 48 | 16 | Camera quaternion XYZW float32 |
| 64 | 4 | Sender processing age in microseconds |
| 68 | 32 | Authentication tag |

Exactly 100 bytes are accepted. Translation is finite and bounded to ±1000 m; quaternion norm must be within 0.01 of unity. Sender processing age above 100 ms is rejected. A sequence is newer only for unsigned delta in `(0, 2^31)`; timestamps must strictly advance within a session. The receiver's local timeout is at most 150 ms.

Fresh key/session files must be generated for each new receiver session because replay history is memory-only. Authentication does not encrypt pose data. The CLI pairing files are developer provisioning, not a consumer pairing flow.

No hand landmarks, calibration updates, anchor pose, clock synchronization or video are transmitted. No production input consumer exists. Processing age and receipt freshness do not establish end-to-end latency; a delayed first packet is an explicit unresolved case for future synchronized transport.
