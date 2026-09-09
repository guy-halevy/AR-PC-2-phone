# Derived-hand transport v2

The Android `HandSender` and Windows `Receiver` share this UDP format. It carries derived geometry, never camera images. Do not confuse it with the older 100-byte HMAC diagnostic pose protocol in `shared/protocol`.

| Byte offset | Length | Meaning |
| --- | --- | --- |
| 0 | 4 | ASCII `PXH2` |
| 4 | 16 | Random PC session ID |
| 20 | 8 | Unsigned sequence, big endian; Android uses the nonnegative signed-long range |
| 28 | 12 | Random per-packet AES-GCM nonce |
| 40 | variable | UTF-8 JSON encrypted with AES-256-GCM, followed by its 16-byte authentication tag |

All 40 header bytes are GCM additional authenticated data. Datagram size is limited to 8192 bytes. The JSON contains `ageMs` (sender processing age), `sentMonoMs` (sender monotonic send time) and at most two `hands`. Each hand contains an ID, confidence, reprojection error in pixels, and 21 XYZ landmarks in meters in the calibrated SteamVR standing frame.

The PC generates a new 32-byte key and 16-byte session on every launch. Its pairing URI encodes JSON with `v:2`, numeric LAN `host`, `port`, URL-safe unpadded base64 `key` and `session`. This URI is secret: possession authorizes hand input when the PC user enables it. Android stores it encrypted with Android KeyStore and disables backup in the derivative manifest.

Android reserves sequence blocks durably before use, leaving unused numbers behind after restart. Fresh random nonces avoid the deterministic nonce-repetition hazard from restoring/clearing counter storage. The PC retains the highest accepted sequence. Restart the PC bridge and pair afresh after Android app-data reset. v1 and v2 are intentionally incompatible.

The receiver validates session, sequence, authentication, schema and timestamp constraints before changing accepted state. An authenticated sender can change its UDP source port after app restart; the paired IP restriction remains. Malformed or unauthenticated traffic cannot refresh the interaction watchdog. Tracking loss, empty hands, stale snapshots and an approximately 150 ms receive timeout release contact through the Windows state machine.

The minimum observed sender/receiver clock offset estimates extra transport delay relative to the best arrival. It cannot measure true one-way delay or establish the absolute freshness of the first packet. There is no independent clock synchronization or challenge exchange. This limitation must not be presented as a complete hostile-network freshness guarantee.

Tests cover authentication, tampering, session/replay rejection, malformed/low-confidence observations, modeled Winsock truncation, real loopback UDP, and authenticated source-port recreation. Android instrumentation checks its real Java encrypted packet against AES-GCM decryption and persistent sequence progression. Physical LAN loss, latency and PC injection still need hardware testing.
