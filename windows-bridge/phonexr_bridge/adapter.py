import copy
import json
import math
import os
from pathlib import Path
import secrets
import struct
import time
from .interaction import validate_panel, project, sub, dot


class Adapter:
    def __init__(self, path):
        self.path = Path(path)
        self.pending = None
        self.request = secrets.randbelow(1 << 52)

    def read(self):
        try:
            if self.path.stat().st_size > 1024*1024:
                raise ValueError('snapshot size')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data['version'] != 1 or not 0 <= time.time()*1000-data['updatedUnixMs'] <= 1000:
                raise ValueError('stale snapshot')
            if len(data['panels']) > 256 or not str(data['sessionId']).isdigit():
                raise ValueError('snapshot bounds')
            usable = []
            for panel in data['panels']:
                if any(type(panel[k]) is not bool for k in ('visible', 'interactive', 'mutable')):
                    raise ValueError('panel flags')
                # Desktop+ also exports unavailable capture sources with zero dimensions.
                # Remove those panels so active interactions release without disabling others.
                if panel['visible'] and (panel['interactive'] or panel['mutable']):
                    validate_panel(panel)
                    if any(not str(panel[k]).isdigit() or not 0 <= int(panel[k]) < 1 << 64 for k in ('id', 'hwnd')):
                        raise ValueError('panel identity')
                    usable.append(panel)
            data['panels'] = usable
            return data
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return None

    def send(self, snapshot, panel, center, right, up, normal, width, now):
        if self.pending:
            if str(snapshot.get('ackRequestId')) == str(self.pending[0]):
                ok = snapshot.get('ackStatus') == 'accepted'
                self.pending = None
                if not ok:
                    return 'rejected'
            elif now-self.pending[1] > .5:
                self.pending = None
                return 'rejected'
            else:
                return 'pending'
        self.request += 1
        matrix = [right[0], up[0], normal[0], center[0], right[1], up[1], normal[1], center[1], right[2], up[2], normal[2], center[2], 0,0,0,1]
        packet = struct.pack('<4sIQQQQ16ff', b'PXR1', 1, int(snapshot['sessionId']), int(panel['id']), panel['revision'], self.request, *matrix, width)
        target = self.path.with_name('command.bin')
        temporary = target.with_name('command.'+secrets.token_hex(8)+'.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(packet)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self.pending = (self.request, now)
        return 'sent'


def length(v):
    return math.sqrt(dot(v,v))


class Manipulator:
    """Border thumb/index pinch translates; two pinches scale and rotate in plane."""
    def __init__(self, adapter):
        self.adapter = adapter
        self.grab = None

    def clear(self):
        self.grab = None

    def frame(self, hands, snapshot, now):
        pinches = {h['id']: h['landmarks'][8] for h in hands if length(sub(h['landmarks'][4], h['landmarks'][8])) < .03}
        panels = snapshot['panels']
        if self.grab is None:
            for hid, point in pinches.items():
                for panel in panels:
                    hit = project(panel, point)
                    if panel['visible'] and panel['mutable'] and hit and abs(hit[2]) < .035 and min(hit[3],hit[4],1-hit[3],1-hit[4]) < .08:
                        ids = [hid]
                        ids += [other for other, pt in pinches.items() if other != hid and project(panel, pt) and abs(project(panel, pt)[2]) < .05]
                        self.grab = dict(panel=copy.deepcopy(panel), session=snapshot['sessionId'], ids=ids, points=[tuple(pinches[i]) for i in ids], revision=panel['revision'])
                        return True
            return False
        g = self.grab
        p = next((p for p in panels if p['id'] == g['panel']['id']), None)
        if p is None or not p['visible'] or not p['mutable'] or snapshot['sessionId'] != g['session'] or any(i not in pinches for i in g['ids']):
            self.clear()
            return True
        # A revision may change only after our own acknowledged command.
        if p['revision'] != g['revision']:
            pending = self.adapter.pending
            if not pending or str(snapshot.get('ackRequestId')) != str(pending[0]) or snapshot.get('ackStatus') != 'accepted':
                self.clear()
                return True
            g['revision'] = p['revision']
        original = g['panel']
        old = g['points']
        new = [pinches[i] for i in g['ids']]
        old_mid = tuple(sum(v[k] for v in old)/len(old) for k in range(3))
        new_mid = tuple(sum(v[k] for v in new)/len(new) for k in range(3))
        center = tuple(original['center'][k]+new_mid[k]-old_mid[k] for k in range(3))
        right, up, normal = original['right'], original['up'], original['normal']
        width = original['widthM']
        if len(old) == 2:
            a,b = sub(old[1],old[0]),sub(new[1],new[0])
            old_span = math.hypot(dot(a, right), dot(a, up))
            new_span = math.hypot(dot(b, right), dot(b, up))
            if old_span < .05 or new_span < .05:
                self.clear()
                return True
            angle = math.atan2(dot(b,up),dot(b,right))-math.atan2(dot(a,up),dot(a,right))
            c,s = math.cos(angle),math.sin(angle)
            right,up = tuple(c*r+s*u for r,u in zip(right,up)), tuple(-s*r+c*u for r,u in zip(right,up))
            width = max(.1,min(5.,width*new_span/old_span))
            # Rotate/scale around the grab midpoint, retaining the grabbed surface points.
            offset = sub(original['center'], old_mid)
            scale = width/original['widthM']
            rx, uy, nz = dot(offset, original['right']), dot(offset, original['up']), dot(offset, normal)
            center = tuple(new_mid[k]+scale*(rx*right[k]+uy*up[k])+nz*normal[k] for k in range(3))
        try:
            status = self.adapter.send(snapshot,p,center,right,up,normal,width,now)
        except (OSError, ValueError, struct.error):
            status = 'rejected'
        if status == 'rejected':
            self.clear()
        return True
