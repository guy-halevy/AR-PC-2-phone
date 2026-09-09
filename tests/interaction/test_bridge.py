import ctypes
import os
import json
import socket
import math
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'windows-bridge'))
from cryptography.exceptions import InvalidTag
from phonexr_bridge.protocol import Receiver
from phonexr_bridge.interaction import ContactEngine, project, validate_panel
from phonexr_bridge.adapter import Adapter, Manipulator
from phonexr_bridge.__main__ import drain
from phonexr_bridge.win32 import WindowsSink, TOUCH


def hand(z=.02, x=0, hid='left'):
    points = [[x,0,z] for _ in range(21)]
    points[4] = [x+.1,0,z]
    return dict(id=hid, confidence=.9, reprojectionErrorPx=1., landmarks=points)


def panel():
    return dict(id='42',revision=1,visible=True,interactive=True,mutable=True,hwnd='0',center=[0,0,0],right=[1,0,0],up=[0,1,0],normal=[0,0,1],widthM=1.,heightM=.5,pixelRect=[-100,20,1000,500])


class Sink:
    def __init__(self):
        self.events=[]
        self.fail=set()
    def valid(self,p,xy): return True
    def emit(self,phase,xy):
        self.events.append((phase,xy))
        return phase not in self.fail


class ProtocolTests(unittest.TestCase):
    def setUp(self): self.receiver=Receiver()
    def packet(self,seq=1,**updates):
        data=dict(ageMs=5.,sentMonoMs=100.,hands=[hand()])
        data.update(updates)
        header=b'PXH2'+self.receiver.session+struct.pack('>Q',seq)+os.urandom(12)
        return header+self.receiver.cipher.encrypt(header[28:40],json.dumps(data).encode(),header)
    def test_authenticated_roundtrip_replay_and_reordering(self):
        self.assertEqual(self.receiver.decode(self.packet(2),200)[0]['id'],'left')
        for seq in (2,1):
            with self.assertRaises(ValueError): self.receiver.decode(self.packet(seq),201)
    def test_tamper_does_not_consume_sequence(self):
        packet=self.packet()
        with self.assertRaises(InvalidTag): self.receiver.decode(packet[:-1]+bytes([packet[-1]^1]),200)
        self.assertEqual(self.receiver.sequence,-1)
        self.receiver.decode(packet,200)
    def test_authenticated_sender_can_reopen_udp_port(self):
        class Socket:
            def __init__(self, packet): self.packet=packet
            def recvfrom(self, size):
                if self.packet is None: raise BlockingIOError()
                packet,self.packet=self.packet,None
                return packet,('127.0.0.1',40002)
        packet=self.packet(2,sentMonoMs=time.monotonic()*1000)
        latest,peer=drain(Socket(packet),self.receiver,('127.0.0.1',40001))
        self.assertEqual(latest[0]['id'],'left')
        self.assertEqual(peer,('127.0.0.1',40002))
        bad=bytearray(self.packet(3,sentMonoMs=time.monotonic()*1000));bad[-1]^=1
        latest,peer=drain(Socket(bytes(bad)),self.receiver,('127.0.0.1',40001))
        self.assertIsNone(latest)
        self.assertEqual(peer,('127.0.0.1',40001))

    def test_session_cannot_be_reset_remotely(self):
        packet=self.packet()
        with self.assertRaises(ValueError): self.receiver.decode(packet[:4]+b'x'*16+packet[20:],200)
    def test_expiry_transport_delay_and_monotonic_rollback(self):
        self.receiver.decode(self.packet(),200)
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(2,sentMonoMs=110),400)
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(2,sentMonoMs=99),210)
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(2,ageMs=151),210)
    def test_confidence_loss_yields_empty_frame(self):
        h=hand(); h['confidence']=.64
        self.assertEqual(self.receiver.decode(self.packet(hands=[h]),200),[])
    def test_invalid_numeric_and_duplicate_identity(self):
        h=hand(); h['landmarks'][8][0]=math.nan
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(hands=[h]),200)
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(hands=[hand(),hand()]),200)
        with self.assertRaises(ValueError): self.receiver.decode(self.packet(ageMs=True),200)


class DatagramTests(unittest.TestCase):
    setUp = ProtocolTests.setUp
    packet = ProtocolTests.packet
    def test_oversized_winsock_datagram_does_not_stop_receiver(self):
        error = OSError('message too long'); error.winerror = 10040
        incoming = [error, (self.packet(), ('192.0.2.1', 1234)), BlockingIOError()]
        class Socket:
            def recvfrom(self, size):
                item = incoming.pop(0)
                if isinstance(item, Exception): raise item
                return item
        hands, peer = drain(Socket(), self.receiver, None)
        self.assertEqual(hands[0]['id'], 'left')
        self.assertEqual(peer, ('192.0.2.1', 1234))

    def test_real_udp_truncation_then_authenticated_frame(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receive, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as send:
            receive.bind(('127.0.0.1', 0)); receive.setblocking(False)
            send.sendto(b'x'*10000, receive.getsockname())
            send.sendto(self.packet(), receive.getsockname())
            hands, peer = drain(receive, self.receiver, None)
            self.assertEqual(hands[0]['id'], 'left')
            self.assertEqual(peer[1], send.getsockname()[1])

    def test_flood_is_bounded_and_unexpected_socket_error_propagates(self):
        class Socket:
            calls = 0
            def recvfrom(self, size):
                self.calls += 1
                return b'invalid', ('192.0.2.1', 1234)
        sock = Socket()
        self.assertEqual(drain(sock, self.receiver, None), (None, None))
        self.assertEqual(sock.calls, 128)
        class Broken:
            def recvfrom(self, size): raise OSError('closed')
        with self.assertRaises(OSError): drain(Broken(), self.receiver, None)


class WindowsContractTests(unittest.TestCase):
    def test_touch_wire_fields_without_injecting_physical_input(self):
        events = []
        class API:
            def InjectTouchInput(self, count, pointer):
                event = ctypes.cast(pointer, ctypes.POINTER(TOUCH)).contents
                events.append((event.pressure, event.pointerInfo.pointerFlags, event.pointerInfo.ptPixelLocation.x))
                return 1
        sink = WindowsSink.__new__(WindowsSink); sink.mouse = False; sink.api = API()
        for phase in ('down', 'update', 'up'): self.assertTrue(sink.emit(phase, (-20, 100)))
        self.assertEqual(events, [(512, 0x10006, -20), (512, 0x20006, -20), (512, 0x40000, -20)])


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.sink=Sink(); self.engine=ContactEngine(self.sink); self.engine.enabled=True
        self.p=panel()
    def frame(self,z,now,x=0): self.engine.frame([hand(z,x)],[self.p],'session',now)
    def press(self): self.frame(.03,0); self.frame(.007,.04)
    def test_coordinate_mapping_and_rigid_validation(self):
        self.assertEqual(project(self.p,[-.5,.25,0])[:2],(-100,20))
        self.assertEqual(project(self.p,[.5,-.25,0])[:2],(899,519))
        self.p['right']=[2,0,0]
        with self.assertRaises(ValueError): validate_panel(self.p)
    def test_no_touch_from_behind_or_without_debounce(self):
        self.frame(-.005,0); self.frame(.001,.04)
        self.assertIsNone(self.engine.active)
        self.engine.hover=None
        self.frame(.02,.1); self.frame(.007,.11)
        self.assertIsNone(self.engine.active)
    def test_down_drag_up_hysteresis(self):
        self.press(); self.frame(.012,.05,.1); self.frame(.017,.06,.2)
        self.assertEqual([e[0] for e in self.sink.events],['down','update','up'])
        self.assertEqual(self.sink.events[-1][1],self.sink.events[-2][1])
    def test_failed_update_release_uses_last_successful_position(self):
        self.press(); position=self.engine.active['xy']; self.sink.fail={'update'}
        self.frame(.008,.06,.2)
        self.assertEqual(self.sink.events[-1],('up',position))
        self.assertIsNone(self.engine.active)
    def test_failed_up_retries_without_new_updates(self):
        self.press(); self.sink.fail={'up'}
        self.frame(.02,.06); self.frame(.005,.07)
        self.assertIsNotNone(self.engine.active)
        self.assertEqual([e[0] for e in self.sink.events],['down','up','up'])
        self.sink.fail=set(); self.engine.tick(.08)
        self.assertIsNone(self.engine.active)
    def test_loss_watchdog_revision_and_disable(self):
        for reason in ('lost','watchdog','revision','disable'):
            self.setUp(); self.press()
            if reason=='lost': self.engine.frame([], [self.p],'session',.05)
            elif reason=='watchdog': self.engine.tick(.191)
            elif reason=='revision': self.p['revision']=2; self.frame(.005,.05)
            else: self.engine.enabled=False; self.engine.tick(.05)
            self.assertIsNone(self.engine.active,reason)
    def test_failed_down_does_not_create_contact(self):
        self.sink.fail={'down'}; self.press()
        self.assertIsNone(self.engine.active)


class AdapterTests(unittest.TestCase):
    def test_fresh_snapshot_and_atomic_command_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'panels.json'; adapter=Adapter(path)
            snapshot=dict(version=1,updatedUnixMs=time.time()*1000,sessionId='123',panels=[panel()])
            path.write_text(json.dumps(snapshot)); self.assertIsNotNone(adapter.read())
            p=panel()
            self.assertEqual(adapter.send(snapshot,p,p['center'],p['right'],p['up'],p['normal'],1.,0),'sent')
            data=(path.parent/'command.bin').read_bytes()
            self.assertEqual(len(data),108)
            unpacked=struct.unpack('<4sIQQQQ16ff',data)
            self.assertEqual(unpacked[:5],(b'PXR1',1,123,42,1))
            self.assertEqual(adapter.send(snapshot,p,p['center'],p['right'],p['up'],p['normal'],1.,.1),'pending')
            snapshot.update(ackRequestId=str(adapter.pending[0]),ackStatus='stale')
            self.assertEqual(adapter.send(snapshot,p,p['center'],p['right'],p['up'],p['normal'],1.,.2),'rejected')
            snapshot['updatedUnixMs']-=2000; path.write_text(json.dumps(snapshot)); self.assertIsNone(adapter.read())
    def test_unavailable_panel_does_not_disable_usable_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'panels.json'
            unavailable = panel(); unavailable.update(id='43', interactive=False, mutable=False, widthM=0, heightM=0, pixelRect=[0,0,0,0])
            snapshot = dict(version=1, updatedUnixMs=time.time()*1000, sessionId='123', panels=[unavailable, panel()])
            path.write_text(json.dumps(snapshot))
            self.assertEqual([p['id'] for p in Adapter(path).read()['panels']], ['42'])

    def test_command_timeout_allows_later_grab_to_recover(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = Adapter(Path(directory)/'panels.json'); p = panel()
            args = (dict(sessionId='123'), p, p['center'], p['right'], p['up'], p['normal'], 1.)
            self.assertEqual(adapter.send(*args, 0), 'sent')
            self.assertEqual(adapter.send(*args, .51), 'rejected')
            self.assertIsNone(adapter.pending)
            self.assertEqual(adapter.send(*args, .6), 'sent')

    def test_two_hand_rotation_and_scale_keep_offset_grab_anchored(self):
        class RecordingAdapter:
            pending = None
            def send(self, *args): self.args = args; return 'sent'
        adapter = RecordingAdapter(); manipulator = Manipulator(adapter)
        def pinch(x, y, hid):
            h = hand(.02, x, hid)
            h['landmarks'][8][1] = y
            h['landmarks'][4] = h['landmarks'][8][:]
            return h
        snapshot = dict(sessionId='1', panels=[panel()])
        self.assertTrue(manipulator.frame([pinch(-.48, .1, 'left'), pinch(.12, .1, 'right')], snapshot, 0))
        # Double the span and rotate 90 degrees around the same off-center midpoint.
        self.assertTrue(manipulator.frame([pinch(-.18, -.5, 'left'), pinch(-.18, .7, 'right')], snapshot, .04))
        self.assertAlmostEqual(adapter.args[5][2], 1.)  # unchanged normal
        self.assertAlmostEqual(adapter.args[6], 2.)
        self.assertAlmostEqual(adapter.args[2][0], .02)
        self.assertAlmostEqual(adapter.args[2][1], .46)
        self.assertAlmostEqual(adapter.args[2][2], 0.)

    def test_border_pinch_and_revision_checked_mutation(self):
        class RecordingAdapter:
            pending=None
            def send(self,*args): self.args=args; return 'sent'
        a=RecordingAdapter(); m=Manipulator(a)
        h=hand(.02,-.48); h['landmarks'][4]=h['landmarks'][8][:]
        snapshot=dict(sessionId='1',panels=[panel()])
        self.assertTrue(m.frame([h],snapshot,0))
        h['landmarks'][8][0]+=.1; h['landmarks'][4][0]+=.1
        self.assertTrue(m.frame([h],snapshot,.04))
        self.assertAlmostEqual(a.args[2][0],.1)
        snapshot['panels'][0]['revision']+=1
        m.frame([h],snapshot,.06)
        self.assertIsNone(m.grab)


if __name__=='__main__': unittest.main()
