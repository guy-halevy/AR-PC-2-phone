import base64
import json
import math
import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


class Receiver:
    def __init__(self, minimum_confidence=.65, maximum_reprojection=8.):
        self.key, self.session, self.prefix = os.urandom(32), os.urandom(16), os.urandom(4)
        self.cipher = AESGCM(self.key)
        self.sequence = -1
        self.offset = None
        self.last_sent = -1
        self.minimum_confidence = minimum_confidence
        self.maximum_reprojection = maximum_reprojection

    def pairing_uri(self, host, port):
        data = dict(v=1, host=host, port=port, key=b64(self.key), session=b64(self.session), noncePrefix=b64(self.prefix))
        return 'phonexr://pair?data=' + b64(json.dumps(data, separators=(',', ':')).encode())

    def decode(self, packet, now_ms):
        if not 44 <= len(packet) <= 8192 or packet[:4] != b'PXH1' or packet[4:20] != self.session:
            raise ValueError('session/header')
        seq = struct.unpack('>Q', packet[20:28])[0]
        if seq <= self.sequence:
            raise ValueError('replay')
        data = json.loads(self.cipher.decrypt(self.prefix + packet[20:28], packet[28:], packet[:28]))
        age, sent = data['ageMs'], data['sentMonoMs']
        if not all(type(v) in (float, int) and math.isfinite(v) for v in (age, sent)) or not 0 <= age <= 150 or sent < self.last_sent:
            raise ValueError('timestamp')
        offset = now_ms - sent
        baseline = offset if self.offset is None else min(offset, self.offset)
        if offset - baseline + age > 150:
            raise ValueError('expired')
        hands = data['hands']
        if not isinstance(hands, list) or len(hands) > 2:
            raise ValueError('hands')
        ids = set()
        accepted = []
        for hand in hands:
            hid, points = hand['id'], hand['landmarks']
            if not isinstance(hid, str) or not 1 <= len(hid) <= 64 or hid in ids or len(points) != 21:
                raise ValueError('identity/landmarks')
            ids.add(hid)
            confidence, reprojection = hand['confidence'], hand['reprojectionErrorPx']
            if not all(type(v) in (int, float) and math.isfinite(v) for v in (confidence, reprojection)) or not 0 <= confidence <= 1 or not 0 <= reprojection <= 10000:
                raise ValueError('confidence/reprojection')
            for point in points:
                if not isinstance(point, list) or len(point) != 3 or not all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 100 for v in point):
                    raise ValueError('coordinate')
            if confidence >= self.minimum_confidence and reprojection <= self.maximum_reprojection:
                accepted.append(hand)
        self.sequence, self.last_sent, self.offset = seq, sent, baseline
        return accepted
