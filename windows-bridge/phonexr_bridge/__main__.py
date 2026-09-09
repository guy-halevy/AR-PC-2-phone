import argparse
import logging
import os
from pathlib import Path
import select
import socket
import time
from cryptography.exceptions import InvalidTag
from .protocol import Receiver
from .adapter import Adapter, Manipulator
from .interaction import ContactEngine
from .win32 import WindowsSink


def drain(sock, receiver, peer):
    """Bound packet work and discard truncated datagrams on both WinSock and POSIX."""
    latest = None
    for _ in range(128):
        try:
            packet, source = sock.recvfrom(8193)
        except BlockingIOError:
            break
        except OSError as error:
            if getattr(error, 'winerror', None) == 10040:  # WSAEMSGSIZE: datagram discarded
                continue
            raise
        if peer is not None and source != peer:
            continue
        try:
            hands = receiver.decode(packet, time.monotonic()*1000)
        except (InvalidTag, ValueError, KeyError, TypeError, OverflowError, RecursionError):
            continue
        peer, latest = source, hands
    return latest, peer


def main():
    parser = argparse.ArgumentParser(description='PhoneXR authenticated hand input bridge (input initially disabled)')
    parser.add_argument('--host', required=True, help='LAN IPv4 address of this PC, embedded in pairing URI')
    parser.add_argument('--port', type=int, default=39571)
    parser.add_argument('--snapshot', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '.'))/'PhoneXR'/'DesktopPlus'/'panels.json')
    parser.add_argument('--mouse-fallback', action='store_true', help='Explicit single-pointer mouse compatibility mode')
    parser.add_argument('--max-reprojection-px', type=float, default=8., help='Calibration reprojection gate (0.1..8 pixels)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    sink = WindowsSink(args.mouse_fallback)
    engine = ContactEngine(sink)
    if not .1 <= args.max_reprojection_px <= 8.:
        parser.error('--max-reprojection-px must be between 0.1 and 8')
    receiver = Receiver(maximum_reprojection=args.max_reprojection_px)
    adapter = Adapter(args.snapshot)
    manipulator = Manipulator(adapter)
    import msvcrt
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.setblocking(False)
    print(receiver.pairing_uri(args.host,args.port), flush=True)
    print('Pairing secret is local and expires on bridge restart. E enables input; D disables; Q exits. Input DISABLED.', flush=True)
    peer = None
    last_hands = None
    try:
        while True:
            now = time.monotonic()
            if msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key == 'q':
                    break
                if key in ('e','d'):
                    engine.enabled = key == 'e'
                    engine.release()
                    manipulator.clear()
                    last_hands = None
                    print('Input '+('ENABLED' if engine.enabled else 'DISABLED'), flush=True)
            snapshot = adapter.read()
            if snapshot is None:
                engine.release()
                manipulator.clear()
            latest, peer = drain(sock, receiver, peer)
            now = time.monotonic()
            if latest is not None:
                last_hands = now
                engine.last_frame = now
                if snapshot is not None and engine.enabled:
                    if engine.active is None and manipulator.frame(latest,snapshot,now):
                        engine.hover = None
                    else:
                        engine.frame(latest,snapshot['panels'],snapshot['sessionId'],now)
            if snapshot is not None and engine.active:
                active = engine.active
                p = next((p for p in snapshot['panels'] if str(p['id']) == active['panel']), None)
                if not p or not p['visible'] or not p['interactive'] or p['revision'] != active['revision'] or snapshot['sessionId'] != active['session'] or not sink.valid(p,active['xy']):
                    engine.release()
            engine.tick(now)
            if last_hands is None or now-last_hands > .150 or not engine.enabled:
                manipulator.clear()
            select.select([sock],[],[],.005)
    except KeyboardInterrupt:
        pass
    finally:
        engine.enabled = False
        for _ in range(10):
            if engine.release():
                break
            time.sleep(.01)
        if engine.active:
            logging.critical('Windows did not accept contact release; input session terminating')
        sock.close()


if __name__ == '__main__':
    main()
