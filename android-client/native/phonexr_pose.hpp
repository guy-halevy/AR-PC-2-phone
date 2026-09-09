#pragma once
#include <cmath>
#include <mutex>

namespace phonexr {
struct Snapshot {
    std::mutex mutex;
    bool enabled = false;
    bool tracking = false;
    bool received = false;
    uint64_t capture = 0;
    AlvrPose pose{{0, 0, 0, 1}, {0, 1.6f, 0}};
};
static Snapshot xr;

// AR pose is capture-time data, never relabeled as a predicted pose.
inline bool readPose(AlvrPose& pose, uint64_t now) {
    std::lock_guard<std::mutex> lock(xr.mutex);
    if (!xr.enabled) return false;
    if (now < xr.capture || now - xr.capture > 150000000ULL) xr.tracking = false;
    pose = xr.pose; // Freeze the last valid pose on loss instead of jumping frames.
    return true;
}
inline bool active() {
    std::lock_guard<std::mutex> lock(xr.mutex);
    return xr.enabled;
}
// 0 = Cardboard mode, 1 = fresh AR snapshot, -1 = AR unavailable/stale.
inline int sampleTracking(AlvrPose& pose, uint64_t& timestamp, uint64_t now) {
    std::lock_guard<std::mutex> lock(xr.mutex);
    if (!xr.enabled) return 0;
    if (!xr.tracking || !xr.received || now < xr.capture || now-xr.capture>150000000ULL) return -1;
    pose=xr.pose; timestamp=xr.capture; return 1;
}
}

extern "C" JNIEXPORT void JNICALL
Java_viritualisres_phonevr_xr_NativeBridge_publishPose(JNIEnv* env, jclass,
        jboolean enabled, jboolean tracking, jlong capture, jfloatArray values) {
    float v[7];
    bool valid = tracking && capture > 0 && values && env->GetArrayLength(values) == 7;
    if (valid) {
        env->GetFloatArrayRegion(values, 0, 7, v);
        for (float x : v) valid = valid && std::isfinite(x);
        const float norm = v[3]*v[3]+v[4]*v[4]+v[5]*v[5]+v[6]*v[6];
        valid = valid && norm > 0.99f && norm < 1.01f;
        for (int i=0;i<3;i++) valid = valid && std::abs(v[i]) <= 100.0f;
    }
    std::lock_guard<std::mutex> lock(phonexr::xr.mutex);
    phonexr::xr.enabled = enabled;
    phonexr::xr.tracking = valid;
    if (valid) {
        phonexr::xr.pose.position[0]=v[0];
        phonexr::xr.pose.position[1]=v[1];
        phonexr::xr.pose.position[2]=v[2];
        phonexr::xr.pose.orientation={v[3],v[4],v[5],v[6]};
        phonexr::xr.capture=static_cast<uint64_t>(capture);
        phonexr::xr.received=true;
    }
}

extern "C" JNIEXPORT jboolean JNICALL
Java_viritualisres_phonevr_xr_NativeBridge_viewerConfigured(JNIEnv*, jclass) {
    uint8_t* data=nullptr;
    int size=0;
    CardboardQrCode_getSavedDeviceParams(&data, &size);
    CardboardQrCode_destroy(data);
    return size > 0;
}
