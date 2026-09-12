"""Require evidence that every PhoneXR instrumentation test executed successfully."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

EXPECTED = {
    'stereoHandRendererDrawsAndRestoresState',
    'syntheticPnPRecoversStandingGeometryAndRejectsBadCalibration',
    'bundledHandModelLoadsAndBlankFrameHasNoHands',
    'senderEncryptsAndReservesNewSequenceRangeAcrossInstances',
    'frameClockRejectsRepeatedFramesAndKeepsArrivalBound',
}

def verify(root):
    passed = set()
    reports = list(root.rglob('TEST-*.xml'))
    if not reports:
        raise ValueError('No Android JUnit XML reports produced')
    for report in reports:
        tree = ET.parse(report)
        for case in tree.iter('testcase'):
            if case.get('classname') != 'viritualisres.phonevr.xr.XrInstrumentationTest':
                continue
            name = case.get('name', '').split('[')[0]
            if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')):
                raise ValueError(f'PhoneXR test failed or skipped: {name}')
            passed.add(name)
    missing = EXPECTED - passed
    if missing:
        raise ValueError('Missing PhoneXR results: ' + ', '.join(sorted(missing)))
    print('Verified PhoneXR Android tests: ' + ', '.join(sorted(passed)))

if __name__ == '__main__':
    verify(Path(sys.argv[1]))
