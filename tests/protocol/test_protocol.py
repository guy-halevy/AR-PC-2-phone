"""Stdlib diagnostic protocol tests; these do not validate Android or SteamVR."""

from dataclasses import replace
import hmac
import importlib.util
import json
import math
from pathlib import Path
import secrets
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.protocol.pose_packet import (
    BODY, MAX_FRESHNESS_NS, MAX_PROCESSING_AGE_US, PACKET_SIZE, PAUSED,
    TRACKING, UINT32_MAX, PacketError, PoseGate, PosePacket, create_pairing,
    decode, encode, load_pairing,
)


def load_tool(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replay = load_tool("phonexr_replay_test", "tools/replay-tool/replay.py")
receiver = load_tool("phonexr_receiver_test", "tools/packet-viewer/receive.py")


class ProtocolTests(unittest.TestCase):
    def test_windows_oversized_datagram_does_not_stop_receiver(self):
        # Model Winsock WSAEMSGSIZE; Linux truncates the same datagram instead.
        class WindowsDatagramSocket:
            def __init__(self, sock):
                self.sock = sock
                self.first = True

            def fileno(self):
                return self.sock.fileno()

            def setblocking(self, value):
                self.sock.setblocking(value)

            def recvfrom(self, size):
                if self.first:
                    self.first = False
                    self.sock.recvfrom(65535)
                    error = OSError("datagram too large")
                    error.winerror = 10040
                    raise error
                return self.sock.recvfrom(size)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiving:
            receiving.bind(("127.0.0.1", 0))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending:
                sending.sendto(bytes(102), receiving.getsockname())
                sending.sendto(self.wire(), receiving.getsockname())
            gate = PoseGate(self.key, self.session)
            count = receiver.run_receiver(WindowsDatagramSocket(receiving), gate,
                                          duration_seconds=0.03, emit=lambda _: None)
            self.assertEqual(count, 1)
            self.assertEqual(gate.latest.sequence, self.packet.sequence)

    def setUp(self):
        self.key = secrets.token_bytes(32)
        self.session = secrets.token_bytes(16)
        self.packet = PosePacket(TRACKING, 7, 123456789, self.session,
                                 (0.4, -0.2, 1.5), (0.0, 0.0, 0.0, 1.0), 500)

    def wire(self, **changes):
        return encode(replace(self.packet, **changes), self.key)

    def signed_fields(self, index, value):
        fields = list(BODY.unpack(self.wire()[:BODY.size]))
        fields[index] = value
        body = BODY.pack(*fields)
        return body + hmac.digest(self.key, body, "sha256")

    def test_exact_wire_layout_and_round_trip(self):
        self.assertEqual(BODY.size, 68)
        wire = self.wire()
        self.assertEqual(len(wire), 100)
        self.assertEqual(PACKET_SIZE, 100)
        self.assertEqual(wire[:4], b"PXRP")
        self.assertEqual(struct.unpack_from("<I", wire, 8)[0], 7)
        self.assertEqual(struct.unpack_from("<Q", wire, 12)[0], 123456789)
        self.assertEqual(wire[20:36], self.session)
        packet = decode(wire, self.key)
        self.assertEqual(packet.sequence, self.packet.sequence)
        self.assertAlmostEqual(packet.translation_m[0], 0.4, places=6)
        self.assertEqual(packet.quaternion_xyzw, self.packet.quaternion_xyzw)

    def test_exact_lengths_and_key_required(self):
        wire = self.wire()
        for length in (0, 67, 68, 99, 101, 2048):
            with self.subTest(length=length), self.assertRaises(PacketError):
                decode((wire + bytes(2048))[:length], self.key)
        for key in (b"", bytes(31), bytes(33), "not a binary key", None):
            with self.subTest(key_type=type(key)), self.assertRaises(PacketError):
                decode(wire, key)

    def test_tamper_every_byte_and_wrong_key(self):
        wire = self.wire()
        for index in range(PACKET_SIZE):
            tampered = bytearray(wire)
            tampered[index] ^= 1
            with self.subTest(index=index), self.assertRaises(PacketError):
                decode(bytes(tampered), self.key)
        with self.assertRaises(PacketError):
            decode(wire, secrets.token_bytes(32))

    def test_authenticated_malformed_values(self):
        changes = [(0, b"FAIL"), (1, 2), (2, 2), (3, 1), (5, 0),
                   (7, math.nan), (8, math.inf), (9, -math.inf),
                   (7, 1000.1), (10, 1.0), (13, 0.0)]
        for index, value in changes:
            with self.subTest(index=index, value=value), self.assertRaises(PacketError):
                decode(self.signed_fields(index, value), self.key)

    def test_encoder_rejects_invalid_shapes_and_ranges(self):
        changes = [dict(state=True), dict(sequence=-1), dict(sequence=2**32),
                   dict(capture_timestamp_ns=2**64), dict(session_id=bytes(15)),
                   dict(processing_age_us=-1), dict(processing_age_us=2**32),
                   dict(translation_m=(0.0, 0.0)),
                   dict(translation_m=(10**10000, 0.0, 0.0)),
                   dict(quaternion_xyzw=(0.0, 0.0, 0.0, 0.0))]
        for change in changes:
            with self.subTest(fields=tuple(change)), self.assertRaises(PacketError):
                self.wire(**change)

    def test_pairing_session_and_processing_age_gate(self):
        gate = PoseGate(self.key, self.session)
        with self.assertRaises(PacketError):
            gate.accept(self.wire(session_id=secrets.token_bytes(16)), 1)
        with self.assertRaises(PacketError):
            gate.accept(self.wire(processing_age_us=MAX_PROCESSING_AGE_US + 1), 1)
        self.assertIsNone(gate.latest)
        gate.accept(self.wire(processing_age_us=MAX_PROCESSING_AGE_US), 1)
        self.assertTrue(gate.tracking)

    def test_replay_reordering_and_old_capture_time(self):
        gate = PoseGate(self.key, self.session)
        gate.accept(self.wire(), 100)
        for sequence, timestamp in ((7, 123456790), (6, 123456790),
                                    (8, 123456789), (8, 123456788),
                                    (7 + 2**31, 123456790)):
            with self.subTest(sequence=sequence, stamp=timestamp), self.assertRaises(PacketError):
                gate.accept(self.wire(sequence=sequence, capture_timestamp_ns=timestamp), 200)
        self.assertEqual(gate.last_received_ns, 100)
        self.assertEqual(gate.latest.sequence, 7)
        gate.accept(self.wire(sequence=8, capture_timestamp_ns=123456790), 200)

    def test_uint32_wrap_and_old_pre_wrap_packet(self):
        gate = PoseGate(self.key, self.session)
        gate.accept(self.wire(sequence=UINT32_MAX), 1)
        gate.accept(self.wire(sequence=0, capture_timestamp_ns=123456790), 2)
        with self.assertRaises(PacketError):
            gate.accept(self.wire(sequence=UINT32_MAX, capture_timestamp_ns=123456791), 3)
        self.assertEqual(gate.latest.sequence, 0)

    def test_pause_timeout_and_resume_without_resetting_replay_guard(self):
        gate = PoseGate(self.key, self.session)
        self.assertFalse(gate.expire(1))
        gate.accept(self.wire(), 10)
        self.assertFalse(gate.expire(10 + MAX_FRESHNESS_NS - 1))
        self.assertTrue(gate.expire(10 + MAX_FRESHNESS_NS))
        self.assertFalse(gate.tracking)
        self.assertFalse(gate.expire(10 + MAX_FRESHNESS_NS + 1))
        with self.assertRaises(PacketError):
            gate.accept(self.wire(), 10 + MAX_FRESHNESS_NS + 2)
        gate.accept(self.wire(sequence=8, capture_timestamp_ns=123456790), 200_000_000)
        self.assertTrue(gate.tracking)
        gate.accept(self.wire(state=PAUSED, sequence=9, capture_timestamp_ns=123456791), 200_000_001)
        self.assertFalse(gate.tracking)
        self.assertFalse(gate.expire(400_000_000))

    def test_watchdog_limit_and_clock_domain_independence(self):
        for timeout in (0, -1, MAX_FRESHNESS_NS + 1):
            with self.assertRaises(PacketError):
                PoseGate(self.key, self.session, timeout)
        gate = PoseGate(self.key, self.session, 100_000_000)
        gate.accept(self.wire(capture_timestamp_ns=2**63), 12)
        self.assertTrue(gate.tracking)  # Sender time is not compared to receiver time.
        with self.assertRaises(PacketError):
            gate.expire(11)

    def test_pairing_files_are_random_and_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="phonexr-pairing-test-") as folder:
            key_file, session_file = Path(folder) / "key", Path(folder) / "session"
            create_pairing(key_file, session_file)
            key, session = load_pairing(key_file, session_file)
            self.assertEqual((len(key), len(session)), (32, 16))
            with self.assertRaises(FileExistsError):
                create_pairing(key_file, session_file)
            self.assertEqual(load_pairing(key_file, session_file), (key, session))
            second_key = Path(folder) / "second-key"
            with self.assertRaises(FileExistsError):
                create_pairing(second_key, session_file)
            self.assertFalse(second_key.exists())
            self.assertEqual(session_file.read_bytes(), session)

    def test_synthetic_endpoint(self):
        start_position, start_q = replay.synthetic_pose(0)
        end_position, end_q = replay.synthetic_pose(1)
        self.assertEqual(start_position, (0.0, 0.0, 0.0))
        self.assertEqual(end_position, (0.4, 0.0, 0.0))
        self.assertAlmostEqual(sum(value * value for value in end_q), 1.0)
        self.assertNotEqual(start_q, end_q)

    def test_real_loopback_synthetic_stream_and_pause(self):
        events, failures = [], []
        stop = threading.Event()
        gate = PoseGate(self.key, self.session)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as inbound:
            inbound.bind(("127.0.0.1", 0))
            destination = inbound.getsockname()
            def receive():
                try:
                    receiver.run_receiver(inbound, gate, stop_event=stop,
                                          emit=lambda event: events.append(json.loads(event)))
                except BaseException as error:
                    failures.append(error)
            thread = threading.Thread(target=receive)
            thread.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as outbound:
                    replay.send_synthetic(outbound, destination, self.key, self.session,
                                          frames=4, rate_hz=60, start_sequence=UINT32_MAX - 1)
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline and not any(
                        event.get("reason") == "sender_paused" for event in events):
                    time.sleep(0.005)
            finally:
                stop.set()
                thread.join(timeout=1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(any(event.get("event") == "diagnostic_pose" for event in events))
        self.assertTrue(any(event.get("reason") == "sender_paused" for event in events))
        self.assertEqual(gate.latest.sequence, 2)
        self.assertAlmostEqual(gate.latest.translation_m[0], 0.4, places=6)
        self.assertFalse(gate.tracking)

    def test_real_loopback_invalid_traffic_does_not_defeat_watchdog(self):
        events, failures = [], []
        stop = threading.Event()
        gate = PoseGate(self.key, self.session, 40_000_000)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as inbound:
            inbound.bind(("127.0.0.1", 0))
            destination = inbound.getsockname()
            def receive():
                try:
                    receiver.run_receiver(inbound, gate, stop_event=stop,
                                          emit=lambda event: events.append(json.loads(event)))
                except BaseException as error:
                    failures.append(error)
            thread = threading.Thread(target=receive)
            thread.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as outbound:
                    outbound.sendto(self.wire(), destination)
                    deadline = time.monotonic() + 0.25
                    while time.monotonic() < deadline:
                        outbound.sendto(b"invalid", destination)
                        if any(event.get("reason") == "local_receipt_timeout" for event in events):
                            break
                        time.sleep(0.005)
            finally:
                stop.set()
                thread.join(timeout=1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(any(event.get("reason") == "local_receipt_timeout" for event in events))
        self.assertFalse(gate.tracking)


if __name__ == "__main__":
    unittest.main()
