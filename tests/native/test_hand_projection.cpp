#include "../../android-client/native/phonexr_projection.hpp"
#include <cassert>
#include <iostream>
#include <limits>
int main(){
    const float pi=3.14159265359f;
    float point[3]={0,1.6f,-1}, left[3]={-.032f,1.6f,0},right[3]={.032f,1.6f,0};
    float q[4]={0,0,0,1}, fov[4]={-pi/4,pi/4,pi/4,-pi/4},l[2],r[2];
    assert(phonexr::projectHandPoint(point,left,q,fov,l));
    assert(phonexr::projectHandPoint(point,right,q,fov,r));
    assert(std::abs(l[0]-.032f)<1e-5f && std::abs(r[0]+.032f)<1e-5f);
    assert(std::abs(l[1])<1e-5f && l[0]>r[0]);
    float far[3]={0,1.6f,-2},farNdc[2];
    assert(phonexr::projectHandPoint(far,left,q,fov,farNdc));
    assert(std::abs(farNdc[0]-l[0]/2)<1e-5f);
    // Translate and yaw the entire configuration: projections must remain identical.
    float translatedEye[3]={4,3.6f,2.032f},translatedPoint[3]={3,3.6f,2};
    float yaw[4]={0,std::sin(pi/4),0,std::cos(pi/4)}, transformed[2];
    assert(phonexr::projectHandPoint(translatedPoint,translatedEye,yaw,fov,transformed));
    assert(std::abs(transformed[0]-l[0])<1e-5f && std::abs(transformed[1]-l[1])<1e-5f);
    float behind[3]={0,1.6f,.1f};assert(!phonexr::projectHandPoint(behind,left,q,fov,l));
    float near[3]={0,1.6f,-.01f};assert(!phonexr::projectHandPoint(near,left,q,fov,l));
    float badQ[4]={0,0,0,2};assert(!phonexr::projectHandPoint(point,left,badQ,fov,l));
    float badFov[4]={0,0,pi/4,-pi/4};assert(!phonexr::projectHandPoint(point,left,q,badFov,l));
    float nan[3]={std::numeric_limits<float>::quiet_NaN(),0,-1};assert(!phonexr::projectHandPoint(nan,left,q,fov,l));
    float asymmetric[4]={-.6f,.9f,.7f,-.4f},center[3]={0,0,0},middle[3]={(std::tan(-.6f)+std::tan(.9f))/2,(std::tan(.7f)+std::tan(-.4f))/2,-1};
    assert(phonexr::projectHandPoint(middle,center,q,asymmetric,l));assert(std::abs(l[0])<1e-5f&&std::abs(l[1])<1e-5f);
    std::cout << "Hand projection: stereo disparity, transformed pose, asymmetric FOV and invalid inputs passed.\n";
}
