#pragma once

// M0 preparation only: dependency-free geometry, not a tracking integration.
// Right-handed coordinates; column vectors; active Hamilton quaternions (x,y,z,w).
// Every position/translation and panel dimension is in metres. No implicit scale.
// T_to_from maps a point expressed in `from` into `to`: p_to = R*p_from + t.
// compose(T_c_b, T_b_a) == T_c_a: the right operand is applied first.
// Frame names are caller-owned; this API cannot statically detect frame mismatch.

#include <algorithm>
#include <cmath>
#include <optional>
#include <stdexcept>

namespace phonexr::math {

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

inline bool is_finite(const Vec3& v) noexcept {
    return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z);
}

inline Vec3 require_finite(Vec3 v) {
    if (!is_finite(v)) {
        throw std::invalid_argument("position must contain finite metres");
    }
    return v;
}

inline Vec3 checked_result(Vec3 v) {
    if (!is_finite(v)) {
        throw std::overflow_error("pose arithmetic exceeded finite range");
    }
    return v;
}

inline Vec3 add(Vec3 a, Vec3 b) {
    require_finite(a);
    require_finite(b);
    return checked_result({a.x + b.x, a.y + b.y, a.z + b.z});
}

// Stored components are immutable to callers and always normalized. Finite,
// nonzero input is normalized; zero and nonfinite quaternions are rejected.
class UnitQuaternion {
public:
    UnitQuaternion() = default;

    static UnitQuaternion from_xyzw(double x, double y, double z, double w) {
        if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z) ||
            !std::isfinite(w)) {
            throw std::invalid_argument("quaternion must be finite");
        }
        const double scale = std::max({std::abs(x), std::abs(y),
                                       std::abs(z), std::abs(w)});
        if (scale == 0.0) {
            throw std::invalid_argument("zero quaternion has no rotation");
        }
        // Scale first so very large and subnormal finite input can normalize.
        x /= scale;
        y /= scale;
        z /= scale;
        w /= scale;
        const double norm = std::sqrt(x*x + y*y + z*z + w*w);
        return UnitQuaternion(x/norm, y/norm, z/norm, w/norm);
    }

    double x() const noexcept { return x_; }
    double y() const noexcept { return y_; }
    double z() const noexcept { return z_; }
    double w() const noexcept { return w_; }

    UnitQuaternion inverse() const noexcept {
        return UnitQuaternion(-x_, -y_, -z_, w_);
    }

    Vec3 rotate(Vec3 v) const {
        require_finite(v);
        const double xx = x_*x_, yy = y_*y_, zz = z_*z_;
        const double xy = x_*y_, xz = x_*z_, yz = y_*z_;
        const double wx = w_*x_, wy = w_*y_, wz = w_*z_;
        return checked_result({
            (1.0-2.0*(yy+zz))*v.x + 2.0*(xy-wz)*v.y + 2.0*(xz+wy)*v.z,
            2.0*(xy+wz)*v.x + (1.0-2.0*(xx+zz))*v.y + 2.0*(yz-wx)*v.z,
            2.0*(xz-wy)*v.x + 2.0*(yz+wx)*v.y + (1.0-2.0*(xx+yy))*v.z
        });
    }

private:
    UnitQuaternion(double x, double y, double z, double w)
        : x_(x), y_(y), z_(z), w_(w) {}

    double x_ = 0.0;
    double y_ = 0.0;
    double z_ = 0.0;
    double w_ = 1.0;
};

inline UnitQuaternion compose(const UnitQuaternion& q_c_b,
                              const UnitQuaternion& q_b_a) {
    const auto& p = q_c_b;
    const auto& q = q_b_a;
    return UnitQuaternion::from_xyzw(
        p.w()*q.x() + p.x()*q.w() + p.y()*q.z() - p.z()*q.y(),
        p.w()*q.y() - p.x()*q.z() + p.y()*q.w() + p.z()*q.x(),
        p.w()*q.z() + p.x()*q.y() - p.y()*q.x() + p.z()*q.w(),
        p.w()*q.w() - p.x()*q.x() - p.y()*q.y() - p.z()*q.z());
}

class Pose {
public:
    Pose() = default;

    // Translation is the `from` frame origin expressed in the `to` frame.
    Pose(Vec3 translation_metres, UnitQuaternion rotation)
        : translation_(require_finite(translation_metres)), rotation_(rotation) {}

    const Vec3& translation_metres() const noexcept { return translation_; }
    const UnitQuaternion& rotation() const noexcept { return rotation_; }

    Vec3 apply(Vec3 point_from_metres) const {
        return add(rotation_.rotate(point_from_metres), translation_);
    }

    Pose inverse() const {
        const auto inverse_rotation = rotation_.inverse();
        return Pose(inverse_rotation.rotate(
                        {-translation_.x, -translation_.y, -translation_.z}),
                    inverse_rotation);
    }

private:
    Vec3 translation_{};
    UnitQuaternion rotation_{};
};

inline Pose compose(const Pose& T_c_b, const Pose& T_b_a) {
    return Pose(T_c_b.apply(T_b_a.translation_metres()),
                compose(T_c_b.rotation(), T_b_a.rotation()));
}

// OpenCV camera: +x right, +y down, +z forward.
// OpenGL/AR camera: +x right, +y up, -z forward.
// p_gl = diag(1,-1,-1)*p_cv. This is a proper 180-degree X rotation,
// not a handedness reflection. Compose it on the side matching frame names.
inline Pose T_camera_gl_camera_cv() {
    return Pose({}, UnitQuaternion::from_xyzw(1.0, 0.0, 0.0, 0.0));
}

// Inputs must share the same AR world and timestamp or a synchronized estimate.
// T_steam_anchor is supplied by independent physical-anchor calibration; it
// must not be inferred from the same synthetic HMD pose this function outputs.
// T_camera_hmd is a measured, fixed camera-to-head extrinsic (HMD points into
// camera coordinates). AR camera inputs use the OpenGL camera convention.
// No default extrinsic is provided: callers must explicitly supply calibration.
inline Pose calibrated_hmd_pose(const Pose& T_ar_camera,
                                const Pose& T_ar_anchor,
                                const Pose& T_steam_anchor,
                                const Pose& T_camera_hmd) {
    const Pose T_anchor_camera = compose(T_ar_anchor.inverse(), T_ar_camera);
    const Pose T_steam_camera = compose(T_steam_anchor, T_anchor_camera);
    return compose(T_steam_camera, T_camera_hmd);
}

struct UV {
    double u;
    double v;
};

// Panel-local rectangle: z=0, origin at centre, +x right, +y up.
// UV origin is top-left: u=x/(width*scale)+0.5, v=0.5-y/(height*scale).
// T_world_panel is rigid (never contains scale); unscaled dimensions are
// multiplied by uniform_scale exactly once. This maps an already known point;
// it does not perform ray intersection, input injection, or focus selection.
// Returns no value off the plane or outside the rectangle. Tiny numerical
// errors at a boundary are clamped; real misses are never projected to an edge.
inline std::optional<UV> panel_uv(Vec3 point_world_metres,
                                  const Pose& T_world_panel,
                                  double width_metres,
                                  double height_metres,
                                  double uniform_scale = 1.0,
                                  double plane_tolerance_metres = 1e-7) {
    if (!std::isfinite(width_metres) || width_metres <= 0.0 ||
        !std::isfinite(height_metres) || height_metres <= 0.0 ||
        !std::isfinite(uniform_scale) || uniform_scale <= 0.0 ||
        !std::isfinite(plane_tolerance_metres) || plane_tolerance_metres < 0.0) {
        throw std::invalid_argument("invalid panel dimensions, scale or tolerance");
    }
    const double width = width_metres * uniform_scale;
    const double height = height_metres * uniform_scale;
    if (!std::isfinite(width) || !std::isfinite(height) ||
        width <= 0.0 || height <= 0.0) {
        throw std::overflow_error("scaled panel dimensions are not representable");
    }
    const Vec3 local = T_world_panel.inverse().apply(point_world_metres);
    if (std::abs(local.z) > plane_tolerance_metres) {
        return std::nullopt;
    }
    const double u = local.x / width + 0.5;
    const double v = 0.5 - local.y / height;
    constexpr double edge_tolerance = 1e-10;
    if (!std::isfinite(u) || !std::isfinite(v) ||
        u < -edge_tolerance || u > 1.0 + edge_tolerance ||
        v < -edge_tolerance || v > 1.0 + edge_tolerance) {
        return std::nullopt;
    }
    return UV{std::clamp(u, 0.0, 1.0), std::clamp(v, 0.0, 1.0)};
}

} // namespace phonexr::math
