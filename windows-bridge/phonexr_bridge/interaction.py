"""Portable geometry and contact lifecycle; OS failures never advance contact state."""
import math


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def validate_panel(p):
    for name in ('center', 'right', 'up', 'normal'):
        v = p[name]
        if len(v) != 3 or not all(math.isfinite(x) and abs(x) < 100 for x in v):
            raise ValueError('panel vector')
    axes = [p[k] for k in ('right', 'up', 'normal')]
    if any(abs(dot(a,a)-1) > .01 for a in axes) or any(abs(dot(axes[i], axes[j])) > .01 for i,j in ((0,1),(0,2),(1,2))):
        raise ValueError('nonrigid panel')
    if not all(math.isfinite(p[k]) and .01 <= p[k] <= 20 for k in ('widthM', 'heightM')):
        raise ValueError('panel size')
    r = p['pixelRect']
    if len(r) != 4 or not all(type(x) is int for x in r) or not 1 <= r[2] <= 65536 or not 1 <= r[3] <= 65536:
        raise ValueError('pixel mapping')
    if not isinstance(p['revision'], int) or p['revision'] < 0:
        raise ValueError('revision')


def project(p, point):
    d = sub(point, p['center'])
    u, v, z = dot(d, p['right']) / p['widthM'] + .5, .5-dot(d, p['up']) / p['heightM'], dot(d, p['normal'])
    if not 0 <= u <= 1 or not 0 <= v <= 1:
        return None
    x,y,w,h = p['pixelRect']
    return round(x+u*(w-1)), round(y+v*(h-1)), z, u, v


class ContactEngine:
    def __init__(self, sink):
        self.sink = sink
        self.active = None
        self.hover = None
        self.enabled = False
        self.last_frame = -math.inf
        self.blocked_until = 0
        self.releasing = False

    def release(self):
        self.hover = None
        if self.active is not None:
            if not self.sink.emit('up', self.active['xy']):
                self.releasing = True
                return False
            self.active = None
        self.releasing = False
        return True

    def tick(self, now):
        if self.releasing or not self.enabled or now-self.last_frame > .150:
            self.release()

    def frame(self, hands, panels, session, now):
        self.last_frame = now
        if self.releasing or not self.enabled:
            self.release()
            return
        live = {str(p['id']): p for p in panels if p['visible'] and p['interactive']}
        if self.active:
            a = self.active
            p = live.get(a['panel'])
            h = next((h for h in hands if h['id'] == a['hand']), None)
            hit = project(p, h['landmarks'][8]) if p and h else None
            if not p or not h or not hit or p['revision'] != a['revision'] or session != a['session'] or hit[2] >= .016 or hit[2] < -.04 or not self.sink.valid(p, hit[:2]):
                if self.release():
                    self.blocked_until = now+.08
                return
            if self.sink.emit('update', hit[:2]):
                a['xy'] = hit[:2]
            else:
                self.release()
            return
        if now < self.blocked_until:
            return
        candidates = []
        for h in hands:
            for p in live.values():
                hit = project(p, h['landmarks'][8])
                if hit and -.01 <= hit[2] <= .08 and self.sink.valid(p, hit[:2]):
                    candidates.append((abs(hit[2]), h, p, hit))
        if not candidates:
            self.hover = None
            return
        _, h, p, hit = min(candidates, key=lambda c:c[0])
        identity = (session, str(p['id']), p['revision'], h['id'])
        if self.hover is None or self.hover['identity'] != identity:
            self.hover = dict(identity=identity, since=now, front=hit[2] >= .016, z=hit[2])
            return
        hover = self.hover
        hover['front'] |= hit[2] >= .016
        if hover['front'] and now-hover['since'] >= .03 and hit[2] <= .008 and hit[2] < hover['z']:
            if self.sink.emit('down', hit[:2]):
                self.active = dict(session=session, panel=str(p['id']), revision=p['revision'], hand=h['id'], xy=hit[:2])
            self.hover = None
        else:
            hover['z'] = hit[2]
