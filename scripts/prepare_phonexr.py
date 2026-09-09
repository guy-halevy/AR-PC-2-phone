"""Integrate the PhoneXR sources into a disposable, baseline-prepared PhoneVR checkout."""
import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
MODEL_SHA = 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'


def edit(path, before, after):
    text = path.read_text()
    if after in text:
        return
    if text.count(before) != 1:
        raise RuntimeError(f'Expected one PhoneXR patch anchor in {path}: {before[:70]}')
    path.write_text(text.replace(before, after, 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phonevr', type=Path)
    parser.add_argument('--model', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    project = args.phonevr / 'code/mobile/android/PhoneVR'
    app = project / 'app'
    java = app / 'src/main/java/viritualisres/phonevr'
    shutil.copytree(repo / 'android-client/src/viritualisres/phonevr/xr', java / 'xr', dirs_exist_ok=True)
    shutil.copy2(repo / 'android-client/native/phonexr_pose.hpp', app / 'src/main/cpp/phonexr_pose.hpp')
    gradle = app / 'build.gradle'
    edit(gradle, "apply plugin: 'com.google.gms.google-services'", "// PhoneXR: no Firebase initialization or analytics plugin")
    edit(gradle, "    implementation platform('com.google.firebase:firebase-bom:26.0.0')\n    implementation 'com.google.firebase:firebase-analytics-ktx'", "    implementation 'com.google.ar:core:1.46.0'\n    implementation 'com.google.mediapipe:tasks-vision:0.10.14'\n    implementation 'org.opencv:opencv:4.10.0'\n    implementation 'com.google.guava:guava:32.1.3-android'")
    edit(gradle, '        applicationId "viritualisres.phonevr"', '        applicationId "org.phonexr.client"')
    manifest = app / 'src/main/AndroidManifest.xml'
    edit(manifest, 'android:name=".ErrorReporting"', 'android:name="android.app.Application"')
    edit(manifest, 'android:allowBackup="true"', 'android:allowBackup="false"')
    edit(manifest, '        <activity\n            android:name=".InitActivity"', '        <meta-data android:name="com.google.ar.core" android:value="optional" />\n        <activity\n            android:name=".InitActivity"')
    activity = java / 'ALVRActivity.java'
    edit(java / 'InitActivity.kt', 'tvVersion.text = "PhoneVR v"', 'tvVersion.text = "PhoneXR dev · PhoneVR v"')
    edit(activity, '    private GLSurfaceView glView;', '    private GLSurfaceView glView;\n    private viritualisres.phonevr.xr.XrController xr;')
    edit(activity, '        Renderer renderer = new Renderer();', '        xr = new viritualisres.phonevr.xr.XrController(this, glView);\n        Renderer renderer = new Renderer();')
    edit(activity, '        pauseNative();\n        glView.onPause();', '        xr.beforePause();\n        pauseNative();\n        glView.onPause();\n        xr.afterPause();')
    edit(activity, '        bMonitor.startMonitoring(this);', '        bMonitor.startMonitoring(this);\n        xr.onResume();')
    edit(activity, '        destroyNative();', '        xr.onDestroy();\n        destroyNative();')
    edit(activity, '            surfaceCreatedNative();', '            surfaceCreatedNative();\n            xr.surfaceCreated();')
    edit(activity, '            setScreenResolutionNative(width, height);', '            setScreenResolutionNative(width, height);\n            xr.surfaceChanged(width, height);')
    edit(activity, '            renderNative();', '            xr.onFrame();\n            renderNative();')
    edit(activity, '        super.onRequestPermissionsResult(requestCode, permissions, grantResults);', '        super.onRequestPermissionsResult(requestCode, permissions, grantResults);\n        if (requestCode == viritualisres.phonevr.xr.XrController.CAMERA_PERMISSION) { xr.onPermissionResult(); return; }')
    cpp = app / 'src/main/cpp/alvr_main.cpp'
    edit(cpp, '#include "utils.h"', '#include "utils.h"\n#include "phonexr_pose.hpp"')
    edit(cpp, '    AlvrPose pose = {};\n\n    float pos[3];', '    AlvrPose pose = {};\n    if (phonexr::readPose(pose, GetBootTimeNano())) return pose;\n\n    float pos[3];')
    edit(cpp, 'outPos[1] -= rotatedOffset[1] - FLOOR_HEIGHT;', 'outPos[1] -= rotatedOffset[1] - (phonexr::active() ? 0.0f : FLOOR_HEIGHT);')
    edit(cpp, 'void updateViewConfigs(uint64_t targetTimestampNs = 0)', 'void updateViewConfigs(uint64_t targetTimestampNs = 0, const AlvrPose* xrPose = nullptr)')
    edit(cpp, '    AlvrPose headPose = getPose(targetTimestampNs);', '    AlvrPose headPose = xrPose ? *xrPose : getPose(targetTimestampNs);')
    edit(cpp, '''        updateViewConfigs(targetTimestampNs);

        alvr_send_tracking(
            targetTimestampNs, CTX.viewParams, &CTX.deviceMotion, 1, nullptr, nullptr);''', '''        AlvrPose xrPose{};
        const int xrState = phonexr::sampleTracking(xrPose, targetTimestampNs, GetBootTimeNano());
        static uint64_t lastXrTimestamp = 0;
        if (xrState == 0 || (xrState == 1 && targetTimestampNs > lastXrTimestamp)) {
            updateViewConfigs(targetTimestampNs, xrState == 1 ? &xrPose : nullptr);
            alvr_send_tracking(targetTimestampNs, CTX.viewParams, &CTX.deviceMotion, 1, nullptr, nullptr);
            if (xrState == 1) lastXrTimestamp = targetTimestampNs;
        }''')
    edit(cpp, '                // offset head pos to Eye Position\n                offsetPosWithQuat', '                // Preserve the AR head translation before applying the eye offset.\n                for (int axis=0; axis<3; ++axis) viewInputs[eye].pose.position[axis]=pose.position[axis];\n                offsetPosWithQuat')
    # No cloud crash reporter is initialized: pairing preferences never enter upstream reports.
    assets = app / 'src/main/assets'
    assets.mkdir(parents=True, exist_ok=True)
    model = args.model.read_bytes() if args.model else urllib.request.urlopen(MODEL_URL, timeout=90).read()
    if hashlib.sha256(model).hexdigest() != MODEL_SHA:
        raise RuntimeError('Hand model checksum mismatch')
    (assets / 'hand_landmarker.task').write_bytes(model)
    print('PhoneXR ARCore/MediaPipe/OpenCV integration applied; real hardware acceptance remains unverified.')


if __name__ == '__main__':
    main()
