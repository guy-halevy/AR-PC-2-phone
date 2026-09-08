#include "../../shared/math/pose.hpp"

#include <array>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

namespace {
using namespace phonexr::math;
int checks = 0;

void expect(bool condition, const std::string& name) {
    ++checks;
    if (!condition) {
        throw std::runtime_error(name);
    }
}

void near(double actual, double expected, const std::string& name,
          double tolerance = 2e-12) {
    expect(std::isfinite(actual) && std::abs(actual - expected) <= tolerance,
           name + " (actual=" + std::to_string(actual) +
           ", expected=" + std::to_string(expected) + ")");
}

void near_vec(Vec3 actual, Vec3 expected, const std::string& name) {
    near(actual.x, expected.x, name + ".x");
    near(actual.y, expected.y, name + ".y");
    near(actual.z, expected.z, name + ".z");
}

template <typename Exception = std::invalid_argument, typename F>
void rejects(F operation, const std::string& name) {
    bool rejected = false;
    try {
        operation();
    } catch (const Exception&) {
        rejected = true;
    }
    expect(rejected, name);
}

void test_rotations() {
    const auto qx = UnitQuaternion::from_xyzw(1, 0, 0, 1);
    const auto qy = UnitQuaternion::from_xyzw(0, 1, 0, 1);
    const auto qz = UnitQuaternion::from_xyzw(0, 0, 1, 1);
    near_vec(qx.rotate({0, 1, 0}), {0, 0, 1}, "+90 X");
    near_vec(qy.rotate({0, 0, 1}), {1, 0, 0}, "+90 Y");
    near_vec(qz.rotate({1, 0, 0}), {0, 1, 0}, "+90 Z");
    near_vec(qz.inverse().rotate({1, 0, 0}), {0, -1, 0}, "-90 Z");
    near_vec(compose(qy, qx).rotate({0, 0, 1}), {0, -1, 0}, "Y after X");
    near_vec(compose(qx, qy).rotate({0, 0, 1}), {1, 0, 0}, "X after Y");
    near_vec(UnitQuaternion::from_xyzw(0, 0, -2, -2).rotate({1, 0, 0}),
             {0, 1, 0}, "quaternion sign equivalence");
    near(qz.x()*qz.x() + qz.y()*qz.y() + qz.z()*qz.z() + qz.w()*qz.w(),
         1.0, "normalization");
    const double huge = std::numeric_limits<double>::max();
    near_vec(UnitQuaternion::from_xyzw(huge, huge, huge, huge).rotate({1, 0, 0}),
             {0, 1, 0}, "large finite normalization");
    const double tiny = std::numeric_limits<double>::denorm_min();
    near_vec(UnitQuaternion::from_xyzw(0, 0, tiny, tiny).rotate({1, 0, 0}),
             {0, 1, 0}, "subnormal normalization");
}

void test_poses() {
    const Pose T_w_b({1, 2, 3}, UnitQuaternion::from_xyzw(0, 0, 1, 1));
    const Pose T_b_c({2, 0, 0}, UnitQuaternion::from_xyzw(1, 0, 0, 1));
    const Pose T_w_c = compose(T_w_b, T_b_c);
    near_vec(T_w_c.translation_metres(), {1, 4, 3}, "composition translation");
    near_vec(T_w_c.apply({0, 1, 0}), {1, 4, 4}, "composition known point");
    near_vec(compose(T_b_c, T_w_b).apply({0, 1, 0}), {2, -3, 2},
             "noncommuting poses");

    const std::array<Vec3, 5> points = {{{0, 0, 0}, {1, 0, 0},
        {0, 1, 0}, {0, 0, 1}, {-2.75, 1.125, 3.375}}};
    const Pose arbitrary({0.13, -2.7, 1.2}, UnitQuaternion::from_xyzw(2, -3, 4, 5));
    for (const auto& point : points) {
        near_vec(Pose().apply(point), point, "identity");
        near_vec(arbitrary.inverse().apply(arbitrary.apply(point)), point,
                 "inverse round trip");
        near_vec(arbitrary.apply(arbitrary.inverse().apply(point)), point,
                 "reverse inverse round trip");
        near_vec(compose(arbitrary, arbitrary.inverse()).apply(point), point,
                 "compose inverse identity");
        near_vec(compose(T_w_c, arbitrary).apply(point),
                 T_w_b.apply(T_b_c.apply(arbitrary.apply(point))),
                 "composition association");
    }
}

void test_calibrated_frames() {
    const Pose T_ar_anchor({10, -3, 2}, UnitQuaternion::from_xyzw(0, 1, 0, 1));
    const Pose T_anchor_camera({1, 0.5, 2}, UnitQuaternion::from_xyzw(0, 0, 1, 1));
    const Pose T_ar_camera = compose(T_ar_anchor, T_anchor_camera);
    const Pose T_steam_anchor({3, 1, -4}, UnitQuaternion::from_xyzw(0, 1, 0, 1));
    const Pose T_camera_hmd({0.03, -0.02, 0.10}, UnitQuaternion());
    const Pose T_steam_hmd = calibrated_hmd_pose(
        T_ar_camera, T_ar_anchor, T_steam_anchor, T_camera_hmd);
    // Head origin: camera offset rotates Z90 -> (0.02,0.03,0.10),
    // then anchor point (1.02,0.53,2.10) rotates Y90 and translates.
    near_vec(T_steam_hmd.translation_metres(), {5.10, 1.53, -5.02},
             "independently calibrated head origin in metres");
    near_vec(T_steam_hmd.apply({1, 0, 0}), {5.10, 2.53, -5.02},
             "calibrated orientation");
    const Pose T_new_ar({20, -12, 7}, UnitQuaternion::from_xyzw(2, 3, -1, 4));
    const Pose rebased = calibrated_hmd_pose(compose(T_new_ar, T_ar_camera),
        compose(T_new_ar, T_ar_anchor), T_steam_anchor, T_camera_hmd);
    near_vec(rebased.translation_metres(), T_steam_hmd.translation_metres(),
             "AR world rebasing invariant");
    near_vec(rebased.apply({0.2, 0.7, -1.2}), T_steam_hmd.apply({0.2, 0.7, -1.2}),
             "AR world rebasing rotation invariant");

    const Pose cv_to_gl = T_camera_gl_camera_cv();
    near_vec(cv_to_gl.apply({1, 2, 3}), {1, -2, -3}, "OpenCV to OpenGL signs");
    near_vec(cv_to_gl.apply({0, 0, 1}), {0, 0, -1}, "camera forward");
    near_vec(compose(cv_to_gl, cv_to_gl).apply({1, 2, 3}), {1, 2, 3},
             "camera convention round trip");
}

void test_panel_uv() {
    const std::array<Pose, 3> placements = {{Pose(),
        Pose({5, -2, 1}, UnitQuaternion::from_xyzw(0, 0, 1, 1)),
        Pose({-3, 4, -7}, UnitQuaternion::from_xyzw(2, -1, 3, 4))}};
    const std::array<double, 4> scales = {{0.25, 1.0, 2.5, 10.0}};
    const std::array<UV, 5> expected = {{{0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5, 0.5}}};
    for (const auto& placement : placements) {
        for (const double scale : scales) {
            for (const auto& uv : expected) {
                // Independent rectangle construction: 2m wide, 1m high.
                const Vec3 local{(uv.u - 0.5)*2.0*scale,
                                 (0.5 - uv.v)*1.0*scale, 0.0};
                const auto actual = panel_uv(placement.apply(local), placement, 2, 1, scale);
                expect(actual.has_value(), "transformed scaled panel point hits");
                near(actual->u, uv.u, "UV u invariant");
                near(actual->v, uv.v, "UV v invariant");
            }
        }
    }
    expect(!panel_uv({1.1, 0, 0}, Pose(), 2, 1), "outside width misses");
    expect(!panel_uv({0, 0.6, 0}, Pose(), 2, 1), "outside height misses");
    expect(!panel_uv({0, 0, 0.01}, Pose(), 2, 1), "off plane misses");
    expect(!panel_uv({0, 0, -0.01}, Pose(), 2, 1), "behind plane misses");
    const auto known = panel_uv({0.5, -0.125, 0}, Pose(), 2, 1, 2);
    expect(known.has_value(), "known scaled interior point");
    near(known->u, 0.625, "known interior u");
    near(known->v, 0.5625, "known interior v");
}

void test_invalid_inputs() {
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    const double huge = std::numeric_limits<double>::max();
    rejects([] { UnitQuaternion::from_xyzw(0, 0, 0, 0); }, "zero quaternion rejected");
    rejects([&] { UnitQuaternion::from_xyzw(nan, 0, 0, 1); }, "NaN quaternion rejected");
    rejects([&] { UnitQuaternion::from_xyzw(0, inf, 0, 1); }, "infinite quaternion rejected");
    rejects([&] { Pose({0, 0, nan}, UnitQuaternion()); }, "NaN translation rejected");
    rejects([&] { Pose({inf, 0, 0}, UnitQuaternion()); }, "infinite translation rejected");
    rejects([&] { Pose().apply({0, nan, 0}); }, "NaN point rejected");
    rejects([&] { UnitQuaternion().rotate({inf, 0, 0}); }, "infinite point rejected");
    rejects<std::overflow_error>([&] {
        Pose({huge, 0, 0}, UnitQuaternion()).apply({huge, 0, 0});
    }, "translation overflow rejected");
    rejects([] { panel_uv({}, Pose(), 0, 1); }, "zero width rejected");
    rejects([] { panel_uv({}, Pose(), 1, -1); }, "negative height rejected");
    rejects([] { panel_uv({}, Pose(), 1, 1, 0); }, "zero scale rejected");
    rejects([] { panel_uv({}, Pose(), 1, 1, -1); }, "negative scale rejected");
    rejects([&] { panel_uv({}, Pose(), nan, 1); }, "NaN dimension rejected");
    rejects([&] { panel_uv({}, Pose(), 1, 1, inf); }, "infinite scale rejected");
    rejects([] { panel_uv({}, Pose(), 1, 1, 1, -1); }, "negative tolerance rejected");
    rejects([&] { panel_uv({}, Pose(), 1, 1, 1, nan); }, "NaN tolerance rejected");
    rejects([&] { panel_uv({nan, 0, 0}, Pose(), 1, 1); }, "NaN panel point rejected");
    rejects<std::overflow_error>([&] { panel_uv({}, Pose(), huge, 1, 2); },
                                 "panel dimension overflow rejected");
    rejects<std::overflow_error>([] {
        panel_uv({}, Pose(), std::numeric_limits<double>::denorm_min(), 1, 0.25);
    }, "panel dimension underflow rejected");
}
} // namespace

int main() {
    try {
        test_rotations();
        test_poses();
        test_calibrated_frames();
        test_panel_uv();
        test_invalid_inputs();
        std::cout << "PASS: " << checks << " deterministic math checks\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "FAIL after " << checks << " checks: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
