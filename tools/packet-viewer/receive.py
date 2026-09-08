"""View authenticated diagnostic poses; NOT a SteamVR bridge or input injector.

Loopback is the default. Only the most recently accepted sample is retained;
no application packet queue is created. The 150 ms watchdog is local receipt
freshness. Sender processing age does NOT measure network transit latency.
"""

from __future__ import annotations

import argparse
import errno
import json
import math
from pathlib import Path
import select
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.protocol.pose_packet import (  # noqa: E402
    PACKET_SIZE, PAUSED, PacketError, PoseGate, load_pairing,
)


def run_receiver(sock: socket.socket, gate: PoseGate, *, duration_seconds=None,
                 stop_event=None, emit=print) -> int:
    """Drain bounded UDP batches, emit latest state, and maintain a watchdog.

    The socket must already be bound. This function never sends a response and
    never changes SteamVR or Windows state. Return accepted packet count.
    """
    if duration_seconds is not None and (
            not math.isfinite(duration_seconds) or duration_seconds <= 0):
        raise ValueError("duration must be positive and finite")
    sock.setblocking(False)
    start = time.monotonic()
    last_print = -math.inf
    last_reject_print = start
    accepted = rejected = 0
    poll_seconds = min(0.02, gate.freshness_timeout_ns / 1e9)
    while stop_event is None or not stop_event.is_set():
        current = time.monotonic()
        if duration_seconds is not None and current - start >= duration_seconds:
            break
        wait_seconds = poll_seconds
        if duration_seconds is not None:
            wait_seconds = min(wait_seconds, max(0, duration_seconds - (current - start)))
        remaining = None
        if gate.tracking and gate.last_received_ns is not None:
            remaining = (gate.last_received_ns + gate.freshness_timeout_ns - time.monotonic_ns()) / 1e9
            wait_seconds = min(wait_seconds, max(0.0, remaining))
        ready, _, _ = select.select([sock], [], [], wait_seconds)
        if gate.expire():
            emit(json.dumps({"event": "tracking_lost", "reason": "local_receipt_timeout"}))
        previous_tracking = gate.tracking
        changed = False
        if ready:
            # Bound work under a flood so invalid packets cannot starve expiry.
            for _ in range(256):
                try:
                    data, _address = sock.recvfrom(PACKET_SIZE + 1)
                except BlockingIOError:
                    break
                except OSError as error:
                    # Winsock consumes oversized UDP datagrams and raises
                    # WSAEMSGSIZE; Unix commonly returns truncated bytes.
                    if (getattr(error, "winerror", None) == 10040
                            or error.errno == errno.EMSGSIZE):
                        rejected += 1
                        continue
                    raise
                try:
                    packet = gate.accept(data)
                except PacketError:
                    rejected += 1
                    continue
                accepted += 1
                changed = True
                if packet.state == PAUSED and previous_tracking:
                    emit(json.dumps({"event": "tracking_lost", "reason": "sender_paused"}))
                previous_tracking = gate.tracking
        if gate.expire():
            emit(json.dumps({"event": "tracking_lost", "reason": "local_receipt_timeout"}))
        current = time.monotonic()
        if changed and (not gate.tracking or current - last_print >= 0.1):
            latest = gate.latest
            emit(json.dumps({
                "event": "diagnostic_pose", "space": "T_ar_from_physical_camera",
                "state": "tracking" if gate.tracking else "paused",
                "sequence": latest.sequence,
                "capture_timestamp_ns_sender": latest.capture_timestamp_ns,
                "translation_m": latest.translation_m,
                "quaternion_xyzw": latest.quaternion_xyzw,
                "sender_processing_age_us": latest.processing_age_us,
            }))
            last_print = current
        if rejected and current - last_reject_print >= 1.0:
            emit(json.dumps({"event": "packets_rejected", "count": rejected}))
            rejected = 0
            last_reject_print = current
    if gate.tracking:
        gate.tracking = False
        emit(json.dumps({"event": "tracking_lost", "reason": "receiver_stopped"}))
    return accepted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9945)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--session-file", required=True)
    parser.add_argument("--timeout-ms", type=int, default=150)
    parser.add_argument("--duration-seconds", type=float)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("port must be within 1..65535")
    try:
        key, session = load_pairing(arguments.key_file, arguments.session_file)
        gate = PoseGate(key, session, arguments.timeout_ms * 1_000_000)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((arguments.bind, arguments.port))
            print("Diagnostic receiver only: no SteamVR or Windows input connection.", flush=True)
            run_receiver(sock, gate, duration_seconds=arguments.duration_seconds,
                         emit=lambda message: print(message, flush=True))
    except (OSError, ValueError, PacketError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
