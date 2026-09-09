package viritualisres.phonevr.xr;

import org.opencv.calib3d.Calib3d;
import org.opencv.core.CvType;
import org.opencv.core.Mat;
import org.opencv.core.MatOfDouble;
import org.opencv.core.MatOfPoint2f;
import org.opencv.core.MatOfPoint3f;
import org.opencv.core.Point;
import org.opencv.core.Point3;

/** Experimental monocular metric estimate; the learned hand scale is not calibrated.
 * Input image points MUST use the unrotated, unmirrored ARCore CPU image grid.
 */
public final class HandPoseEstimator {
    public HandObservation estimate(int id, float confidence, float[] modelXyz,
                                    float[] imageXy, float[] intrinsics,
                                    float[] cameraToStanding, int width, int height, float handScale) {
        if (!finite(modelXyz, 63) || !finite(imageXy, 42)
                || !validCalibration(intrinsics, cameraToStanding) || width <= 0 || height <= 0
                || !Float.isFinite(handScale) || handScale < 0.5f || handScale > 1.5f
                || !Float.isFinite(confidence) || confidence < 0.65f) return null;
        // Broad anatomical plausibility checks reject broken geometry, not personalize scale.
        double palm = distance(modelXyz, 0, 9);
        double breadth = distance(modelXyz, 5, 17);
        if (palm < 0.025 || palm > 0.15 || breadth < 0.025 || breadth > 0.16) return null;
        Point3[] objects = new Point3[21];
        Point[] pixels = new Point[21];
        double minX = width, maxX = 0, minY = height, maxY = 0;
        for (int i = 0; i < 21; i++) {
            objects[i] = new Point3(modelXyz[i*3], modelXyz[i*3+1], modelXyz[i*3+2]);
            double x = imageXy[i*2], y = imageXy[i*2+1];
            if (x < 0 || x >= width || y < 0 || y >= height) return null;
            pixels[i] = new Point(x, y);
            minX = Math.min(minX, x); maxX = Math.max(maxX, x);
            minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        }
        double diagonal = Math.hypot(maxX-minX, maxY-minY);
        if (diagonal < 30) return null;
        MatOfPoint3f objectMat = new MatOfPoint3f(objects);
        MatOfPoint2f imageMat = new MatOfPoint2f(pixels);
        Mat camera = Mat.eye(3, 3, CvType.CV_64F);
        MatOfDouble distortion = new MatOfDouble(0, 0, 0, 0, 0);
        Mat rvec = new Mat(), tvec = new Mat(), rotation = new Mat();
        try {
            camera.put(0, 0, intrinsics[0]); camera.put(1, 1, intrinsics[1]);
            camera.put(0, 2, intrinsics[2]); camera.put(1, 2, intrinsics[3]);
            if (!Calib3d.solvePnP(objectMat, imageMat, camera, distortion, rvec, tvec,
                    false, Calib3d.SOLVEPNP_EPNP)) return null;
            if (!Calib3d.solvePnP(objectMat, imageMat, camera, distortion, rvec, tvec,
                    true, Calib3d.SOLVEPNP_ITERATIVE)) return null;
            Calib3d.Rodrigues(rvec, rotation);
            double[] r = new double[9], t = new double[3];
            rotation.get(0, 0, r); tvec.get(0, 0, t);
            float[] standing = new float[63];
            double squaredError = 0, maxError = 0;
            for (int i = 0; i < 21; i++) {
                Point3 p = objects[i];
                double x = r[0]*p.x + r[1]*p.y + r[2]*p.z + t[0];
                double y = r[3]*p.x + r[4]*p.y + r[5]*p.z + t[1];
                double z = r[6]*p.x + r[7]*p.y + r[8]*p.z + t[2];
                if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(z)
                        || z*handScale < 0.10 || z*handScale > 2.0) return null;
                double error = Math.hypot(intrinsics[0]*x/z + intrinsics[2] - pixels[i].x,
                        intrinsics[1]*y/z + intrinsics[3] - pixels[i].y);
                squaredError += error*error; maxError = Math.max(maxError, error);
                // Scaling both hand geometry and camera-relative translation preserves projection.
                x *= handScale; y *= handScale; z *= handScale;
                // OpenCV -> physical OpenGL camera is diag(1,-1,-1).
                for (int axis = 0; axis < 3; axis++) {
                    float value = (float)(cameraToStanding[axis]*x - cameraToStanding[4+axis]*y
                            - cameraToStanding[8+axis]*z + cameraToStanding[12+axis]);
                    if (!Float.isFinite(value)) return null;
                    standing[i*3+axis] = value;
                }
            }
            double rms = Math.sqrt(squaredError/21);
            double limit = Math.max(3, Math.min(10, diagonal*0.035));
            if (rms > limit || maxError > limit*2.5) return null;
            return new HandObservation(id, confidence, standing, (float)rms);
        } finally {
            objectMat.release(); imageMat.release(); camera.release(); distortion.release();
            rvec.release(); tvec.release(); rotation.release();
        }
    }

    static boolean finite(float[] values, int count) {
        if (values == null || values.length != count) return false;
        for (float value : values) if (!Float.isFinite(value)) return false;
        return true;
    }

    static boolean validCalibration(float[] k, float[] transform) {
        if (!finite(k, 4) || !finite(transform, 16) || k[0] <= 0 || k[1] <= 0) return false;
        if (Math.abs(transform[3]) > 0.001 || Math.abs(transform[7]) > 0.001
                || Math.abs(transform[11]) > 0.001 || Math.abs(transform[15]-1) > 0.001) return false;
        for (int a = 0; a < 3; a++) for (int b = a; b < 3; b++) {
            double dot = 0;
            for (int row = 0; row < 3; row++) dot += transform[a*4+row]*transform[b*4+row];
            if (Math.abs(dot-(a == b ? 1 : 0)) > 0.02) return false;
        }
        double det = transform[0]*(transform[5]*transform[10]-transform[9]*transform[6])
                - transform[4]*(transform[1]*transform[10]-transform[9]*transform[2])
                + transform[8]*(transform[1]*transform[6]-transform[5]*transform[2]);
        return Math.abs(det-1) < 0.03;
    }

    private static double distance(float[] p, int a, int b) {
        double x = p[a*3]-p[b*3], y = p[a*3+1]-p[b*3+1], z = p[a*3+2]-p[b*3+2];
        return Math.sqrt(x*x+y*y+z*z);
    }
}
