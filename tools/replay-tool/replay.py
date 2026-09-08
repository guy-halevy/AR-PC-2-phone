"""Send SYNTHETIC diagnostic poses; not recorded camera data or a SteamVR client.

The sequence moves 0.4 m along X while yaw changes by 30 degrees. No camera,
Android, Windows input, or SteamVR connection is implemented by this tool.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.protocol.pose_packet import (  # noqa: E402
    PAUSED, TRACKING, UINT32_MAX, PacketError, PosePacket, encode, load_pairing,
)


def synthetic_pose(progress: float) -> tuple[tuple, tuple]:
    """Return a deterministic synthetic camera pose, progress in [0, 1]."""
    if not math.isfinite(progress) or not 0.0 <= progress <= 1.0:
        raise ValueError("progress must be within [0, 1]")
    half_yaw = math.radians(30.0) * progress * 0.5
    return (0.4 * progress, 0.0, 0.0), (0.0, math.sin(half_yaw), 0.0, math.cos(half_yaw))


def send_synthetic(sock: socket.socket, destination: tuple[str, int], key: bytes,
                   session_id: bytes, frames: int = 120, rate_hz: float = 30.0,
                   start_sequence: int = 0) -> int:
    """Send paced samples then PAUSED. Pairing/replay counters are session-local."""
    if type(frames) is not int or frames < 2:
        raise ValueError("frames must be an integer of at least 2")
    if not math.isfinite(rate_hz) or not 1.0 <= rate_hz <= 60.0:
        raise ValueError("rate must be within 1..60 Hz")
    if type(start_sequence) is not int or not 0 <= start_sequence <= UINT32_MAX:
        raise ValueError("start sequence must be uint32")
    start = time.monotonic()
    last_stamp = 0
    for index in range(frames + 1):
        remaining = start + index / rate_hz - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        stamp = max(time.monotonic_ns(), last_stamp + 1)
        last_stamp = stamp
        position, quaternion = synthetic_pose(min(index, frames - 1) / (frames - 1))
        age = max(0, (time.monotonic_ns() - stamp) // 1000)
        packet = PosePacket(
            TRACKING if index < frames else PAUSED,
            (start_sequence + index) & UINT32_MAX, stamp, session_id,
            position, quaternion, age,
        )
        sock.sendto(encode(packet, key), destination)
    return frames + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9945)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--session-file", required=True)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--rate-hz", type=float, default=30.0)
    parser.add_argument("--start-sequence", type=int, default=0)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("port must be within 1..65535")
    try:
        key, session = load_pairing(arguments.key_file, arguments.session_file)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            count = send_synthetic(
                sock, (arguments.host, arguments.port), key, session,
                arguments.frames, arguments.rate_hz, arguments.start_sequence,
            )
    except (OSError, ValueError, PacketError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        return 130
    print(f"Sent {count} SYNTHETIC diagnostic packets including final PAUSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
