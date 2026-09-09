// Exercise the actual native snapshot code with narrow JNI/Cardboard test doubles.
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>
#define JNIEXPORT
#define JNICALL
using jboolean = bool;
using jlong = int64_t;
using jclass = void*;
using jfloatArray = std::vector<float>*;
struct JNIEnv {
    int GetArrayLength(jfloatArray v) { return static_cast<int>(v->size()); }
    void GetFloatArrayRegion(jfloatArray v, int start, int count, float* out) {
        std::copy_n(v->begin()+start, count, out);
    }
};
struct Quaternion { float x,y,z,w; };
struct AlvrPose { Quaternion orientation; float position[3]; };
void CardboardQrCode_getSavedDeviceParams(uint8_t**, int* size) { *size=0; }
void CardboardQrCode_destroy(uint8_t*) {}
#include "../../android-client/native/phonexr_pose.hpp"
int main() {
    JNIEnv env;
    AlvrPose result{};
    uint64_t timestamp=999;
    constexpr uint64_t capture=1000000000;
    auto publish=[&](bool enabled,bool tracking,int64_t time,jfloatArray v) {
        Java_viritualisres_phonevr_xr_NativeBridge_publishPose(&env,nullptr,enabled,tracking,time,v);
    };
    assert(phonexr::sampleTracking(result,timestamp,capture)==0);
    publish(true,false,0,nullptr);
    assert(phonexr::sampleTracking(result,timestamp,capture)==-1);
    std::vector<float> pose={1,1.7f,-2,0,0,0,1};
    publish(true,true,capture,&pose);
    assert(phonexr::sampleTracking(result,timestamp,capture+100)==1);
    assert(timestamp==capture && result.position[0]==1 && result.position[2]==-2);
    timestamp=999;
    assert(phonexr::sampleTracking(result,timestamp,capture+150000001)==-1);
    assert(timestamp==999); // stale data must not be stamped with a new target time
    assert(phonexr::readPose(result,capture+150000001));
    assert(result.position[0]==1); // rendering freezes instead of jumping to zero
    publish(true,true,capture+200000000,&pose);
    assert(phonexr::sampleTracking(result,timestamp,capture+200000100)==1);
    assert(phonexr::sampleTracking(result,timestamp,capture-1)==-1);
    pose[0]=std::numeric_limits<float>::quiet_NaN();
    publish(true,true,capture+300000000,&pose);
    assert(phonexr::sampleTracking(result,timestamp,capture+300000100)==-1);
    phonexr::readPose(result,capture+300000100);
    assert(result.position[0]==1);
    pose[0]=0;pose[6]=2;
    publish(true,true,capture+400000000,&pose);
    assert(phonexr::sampleTracking(result,timestamp,capture+400000100)==-1);
    publish(false,false,0,nullptr);
    assert(!phonexr::active());
    assert(!phonexr::readPose(result,capture));
    assert(phonexr::sampleTracking(result,timestamp,capture)==0);
    std::cout << "Native snapshot: capture time, freshness, freeze, recovery and validation passed\n";
}
