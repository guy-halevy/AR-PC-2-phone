#pragma once
#include <cmath>

namespace phonexr {
// Eye pose is standing-from-eye, quaternion xyzw. FOV angles are radians.
inline bool projectHandPoint(const float* point, const float* position, const float* q,
                             const float* fov, float* ndc) {
    for (int i=0;i<3;++i) if (!std::isfinite(point[i]) || !std::isfinite(position[i])) return false;
    float norm=0;
    for (int i=0;i<4;++i) {
        if (!std::isfinite(q[i]) || !std::isfinite(fov[i]) || std::abs(fov[i])>=1.56f) return false;
        norm+=q[i]*q[i];
    }
    if (std::abs(norm-1)>0.01f) return false;
    const float l=std::tan(fov[0]), r=std::tan(fov[1]), u=std::tan(fov[2]), d=std::tan(fov[3]);
    if (r-l<0.001f || u-d<0.001f) return false;
    float v[3]={point[0]-position[0],point[1]-position[1],point[2]-position[2]};
    // Rotate by the conjugate quaternion to obtain eye-space coordinates.
    const float x=-q[0],y=-q[1],z=-q[2];
    float t[3]={2*(y*v[2]-z*v[1]),2*(z*v[0]-x*v[2]),2*(x*v[1]-y*v[0])};
    float camera[3]={v[0]+q[3]*t[0]+y*t[2]-z*t[1],
                     v[1]+q[3]*t[1]+z*t[0]-x*t[2],
                     v[2]+q[3]*t[2]+x*t[1]-y*t[0]};
    if (camera[2]>=-0.03f) return false;
    ndc[0]=(2*camera[0]/-camera[2]-r-l)/(r-l);
    ndc[1]=(2*camera[1]/-camera[2]-u-d)/(u-d);
    return std::isfinite(ndc[0]) && std::isfinite(ndc[1]);
}
}
