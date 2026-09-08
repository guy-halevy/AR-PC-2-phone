"""Authenticated diagnostic pose transport; NOT connected to SteamVR or input.

Wire format is exactly 100 bytes: struct '<4sBBHIQ16s7fI' (68 bytes),
followed by HMAC-SHA256 (32 bytes). Pose is T_ar_from_physical_camera:
translation xyz in meters and quaternion xyzw, never a SteamVR pose.

The capture timestamp is in the sender's monotonic clock domain. There is no
clock synchronization: processing_age_us measures sender processing only, and
the receiver watchdog measures time since receipt, NOT network transit time.
Authentication provides integrity, not encryption. Use fresh pairing material
for each new receiver session; replay history is deliberately memory-only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import hmac
import math
import os
from pathlib import Path
import secrets
import struct
import time


BODY = struct.Struct("<4sBBHIQ16s7fI")
MAGIC = b"PXRP"
VERSION = 1
PACKET_SIZE = BODY.size + hashlib.sha256().digest_size
PAUSED = 0
TRACKING = 1
MAX_PROCESSING_AGE_US = 100_000
MAX_FRESHNESS_NS = 150_000_000
MAX_TRANSLATION_METERS = 1000.0
QUATERNION_NORM_TOLERANCE = 0.01
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1


class PacketError(ValueError):
    """Malformed, unauthenticated, or stale diagnostic sample."""


def _bytes_of_length(value: bytes, size: int, label: str) -> bytes:
    if not isinstance(value, bytes) or len(value) != size:
        raise PacketError(f"{label} must contain exactly {size} bytes")
    return value


def _uint(value: int, maximum: int, label: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise PacketError(f"{label} is outside [{minimum}, {maximum}]")
    return value


def _vector(values: tuple, size: int, limit: float, label: str) -> None:
    if not isinstance(values, tuple) or len(values) != size:
        raise PacketError(f"{label} requires {size} components")
    for value in values:
        if type(value) not in (float, int):
            raise PacketError(f"{label} components must be numeric")
        try:
            valid = math.isfinite(value) and abs(value) <= limit
        except OverflowError:
            valid = False
        if not valid:
            raise PacketError(f"{label} contains a nonfinite or out-of-range value")


@dataclass(frozen=True)
class PosePacket:
    state: int
    sequence: int
    capture_timestamp_ns: int
    session_id: bytes
    translation_m: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]
    processing_age_us: int = 0

    def validate(self) -> None:
        _uint(self.state, TRACKING, "state")
        _uint(self.sequence, UINT32_MAX, "sequence")
        _uint(self.capture_timestamp_ns, UINT64_MAX, "capture timestamp", 1)
        _bytes_of_length(self.session_id, 16, "session ID")
        _uint(self.processing_age_us, UINT32_MAX, "processing age")
        _vector(self.translation_m, 3, MAX_TRANSLATION_METERS, "translation")
        _vector(self.quaternion_xyzw, 4, 1.01, "quaternion")
        norm = math.sqrt(sum(value * value for value in self.quaternion_xyzw))
        if abs(norm - 1.0) > QUATERNION_NORM_TOLERANCE:
            raise PacketError("quaternion must have unit norm within 0.01")


def encode(packet: PosePacket, key: bytes) -> bytes:
    """Encode one authenticated diagnostic sample. No encryption is applied."""
    _bytes_of_length(key, 32, "pairing key")
    if not isinstance(packet, PosePacket):
        raise PacketError("packet must be a PosePacket")
    packet.validate()
    body = BODY.pack(
        MAGIC, VERSION, packet.state, 0, packet.sequence,
        packet.capture_timestamp_ns, packet.session_id,
        *packet.translation_m, *packet.quaternion_xyzw, packet.processing_age_us,
    )
    return body + hmac.digest(key, body, "sha256")


def decode(data: bytes, key: bytes) -> PosePacket:
    """Verify length and HMAC before interpreting untrusted packet fields."""
    _bytes_of_length(key, 32, "pairing key")
    _bytes_of_length(data, PACKET_SIZE, "packet")
    body, supplied_mac = data[:BODY.size], data[BODY.size:]
    if not hmac.compare_digest(supplied_mac, hmac.digest(key, body, "sha256")):
        raise PacketError("packet authentication failed")
    fields = BODY.unpack(body)
    magic, version, state, reserved, sequence, stamp, session = fields[:7]
    if magic != MAGIC or version != VERSION or reserved != 0:
        raise PacketError("unsupported magic, version, or reserved field")
    packet = PosePacket(
        state, sequence, stamp, session, tuple(fields[7:10]),
        tuple(fields[10:14]), fields[14],
    )
    packet.validate()
    return packet


def sequence_is_newer(sequence: int, previous: int) -> bool:
    """RFC1982-style uint32 comparison; exactly half a range is ambiguous."""
    delta = (sequence - previous) & UINT32_MAX
    return 0 < delta < (1 << 31)


class PoseGate:
    """One-session replay gate and local liveness watchdog; stores one sample.

    A valid but delayed first packet cannot be identified as network-stale
    without clock synchronization. A sender restart must create a fresh key
    and session rather than resetting the replay counters in this object.
    """

    def __init__(self, key: bytes, session_id: bytes,
                 freshness_timeout_ns: int = MAX_FRESHNESS_NS):
        self._key = _bytes_of_length(key, 32, "pairing key")
        self.session_id = _bytes_of_length(session_id, 16, "session ID")
        self.freshness_timeout_ns = _uint(
            freshness_timeout_ns, MAX_FRESHNESS_NS, "freshness timeout", 1,
        )
        self.latest: PosePacket | None = None
        self.last_received_ns: int | None = None
        self.tracking = False

    def accept(self, data: bytes, now_ns: int | None = None) -> PosePacket:
        now_ns = time.monotonic_ns() if now_ns is None else now_ns
        _uint(now_ns, UINT64_MAX, "receiver monotonic timestamp")
        if self.last_received_ns is not None and now_ns < self.last_received_ns:
            raise PacketError("receiver monotonic clock moved backwards")
        packet = decode(data, self._key)
        if not hmac.compare_digest(packet.session_id, self.session_id):
            raise PacketError("unexpected pairing session")
        if packet.processing_age_us > MAX_PROCESSING_AGE_US:
            raise PacketError("sender processing age exceeds 100 ms")
        if self.latest is not None:
            if not sequence_is_newer(packet.sequence, self.latest.sequence):
                raise PacketError("replayed, ambiguous, or reordered sequence")
            if packet.capture_timestamp_ns <= self.latest.capture_timestamp_ns:
                raise PacketError("capture timestamp did not advance")
        self.latest = packet
        self.last_received_ns = now_ns
        self.tracking = packet.state == TRACKING
        return packet

    def expire(self, now_ns: int | None = None) -> bool:
        """Return True exactly when tracking transitions to locally timed out."""
        now_ns = time.monotonic_ns() if now_ns is None else now_ns
        _uint(now_ns, UINT64_MAX, "receiver monotonic timestamp")
        if self.last_received_ns is not None and now_ns < self.last_received_ns:
            raise PacketError("receiver monotonic clock moved backwards")
        if (self.tracking and self.last_received_ns is not None
                and now_ns - self.last_received_ns >= self.freshness_timeout_ns):
            self.tracking = False
            return True
        return False


def load_pairing(key_file: str | Path, session_file: str | Path) -> tuple[bytes, bytes]:
    """Read explicitly supplied raw binary pairing files, without printing them."""
    key = _bytes_of_length(Path(key_file).read_bytes(), 32, "pairing key file")
    session = _bytes_of_length(Path(session_file).read_bytes(), 16, "session file")
    return key, session


def create_pairing(key_file: str | Path, session_file: str | Path) -> None:
    """Create fresh random raw-binary pairing files, refusing to overwrite.

    Files are mode 0600 where the operating system supports POSIX modes.
    The caller must use an appropriately private directory on Windows.
    """
    paths = [Path(key_file), Path(session_file)]
    if paths[0].absolute() == paths[1].absolute():
        raise PacketError("key and session require different file paths")
    created = []
    try:
        for path, size in zip(paths, (32, 16)):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(secrets.token_bytes(size))
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-pairing"])
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--session-file", required=True)
    arguments = parser.parse_args()
    try:
        create_pairing(arguments.key_file, arguments.session_file)
    except (OSError, PacketError) as error:
        parser.error(str(error))
    print("Created fresh diagnostic pairing files. Keep the key private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
