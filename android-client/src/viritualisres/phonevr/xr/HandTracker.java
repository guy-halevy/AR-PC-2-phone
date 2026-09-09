package viritualisres.phonevr.xr;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.media.Image;
import android.os.SystemClock;
import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.components.containers.Category;
import com.google.mediapipe.tasks.components.containers.Landmark;
import com.google.mediapipe.tasks.components.containers.NormalizedLandmark;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.core.Delegate;
import com.google.mediapipe.tasks.vision.core.RunningMode;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.opencv.core.Core;

/** Local CPU inference on one bounded worker. No camera ownership or image transmission.
 * Listener callbacks are serialized under the lifecycle lock, may run on the worker or
 * invalidating caller thread, and must be quick/nonblocking (post UI work to the UI thread).
 */
public final class HandTracker implements AutoCloseable {
    public interface Listener {
        void onHands(List<HandObservation> hands, long captureElapsedNs);
        void onError(String message);
    }

    private final Context context;
    private final Listener listener;
    private final Object lock = new Object();
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(1, 1, 0,
            TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(2), r -> {
                Thread thread = new Thread(r, "PhoneXR-HandTracker");
                thread.setPriority(Thread.NORM_PRIORITY - 1);
                return thread;
            });
    private final HandPoseEstimator estimator = new HandPoseEstimator();
    private HandLandmarker landmarker; // Accessed only on the worker.
    private boolean closed, busy, failed;
    private long generation, lastVideoMs = -1;
    private float handScale = 1.0f;
    private static final long MAX_RESULT_AGE_NS = 150_000_000L;

    public HandTracker(Context context, Listener listener) {
        if (context == null || listener == null) throw new IllegalArgumentException("Context/listener");
        this.context = context.getApplicationContext();
        this.listener = listener;
    }

    /** True transfers image ownership, even if conversion subsequently fails. False leaves
     * ownership with caller. An accepted image is always closed before this method returns.
     * Intrinsics and transform must match this exact raw physical-camera exposure.
     */
    public boolean submit(Image image, float[] intrinsicsFxFyCxCy,
                          float[] cameraToStanding16, long captureElapsedNs) {
        synchronized (lock) {
            if (closed || failed || busy || image == null || captureElapsedNs <= 0
                    || !HandPoseEstimator.validCalibration(intrinsicsFxFyCxCy, cameraToStanding16)) return false;
            busy = true;
            final YuvFrame frame;
            try {
                frame = YuvFrame.copy(image);
            } catch (RuntimeException error) {
                busy = false;
                listener.onError("Hand image conversion failed: " + error.getMessage());
                listener.onHands(Collections.emptyList(), captureElapsedNs);
                return true;
            } finally {
                image.close();
            }
            final long token = generation;
            final float scale = handScale;
            final float[] intrinsics = intrinsicsFxFyCxCy.clone();
            final float[] cameraToStanding = cameraToStanding16.clone();
            worker.execute(() -> process(frame, intrinsics, cameraToStanding, captureElapsedNs, token, scale));
            return true;
        }
    }

    private void process(YuvFrame frame, float[] intrinsics, float[] transform,
                         long captureElapsedNs, long token, float scale) {
        Bitmap bitmap = null;
        MPImage mpImage = null;
        try {
            synchronized (lock) { if (closed || generation != token) return; }
            if (landmarker == null) {
                System.loadLibrary(Core.NATIVE_LIBRARY_NAME);
                BaseOptions base = BaseOptions.builder().setModelAssetPath("hand_landmarker.task")
                        .setDelegate(Delegate.CPU).build();
                landmarker = HandLandmarker.createFromOptions(context,
                        HandLandmarker.HandLandmarkerOptions.builder().setBaseOptions(base)
                                .setRunningMode(RunningMode.VIDEO).setNumHands(2)
                                .setMinHandDetectionConfidence(0.6f)
                                .setMinHandPresenceConfidence(0.6f)
                                .setMinTrackingConfidence(0.6f).build());
            }
            bitmap = frame.toBitmap();
            mpImage = new BitmapImageBuilder(bitmap).build();
            // VIDEO requires strictly increasing milliseconds; original nanoseconds are
            // preserved separately for freshness and the returned observation timestamp.
            long videoMs = Math.max(lastVideoMs + 1, captureElapsedNs / 1_000_000L);
            lastVideoMs = videoMs;
            HandLandmarkerResult result = landmarker.detectForVideo(mpImage, videoMs);
            HandObservation[] bySide = new HandObservation[2];
            for (int hand = 0; hand < Math.min(2, result.landmarks().size()); hand++) {
                if (hand >= result.worldLandmarks().size() || hand >= result.handedness().size()
                        || result.handedness().get(hand).isEmpty()) continue;
                Category category = result.handedness().get(hand).get(0);
                int id;
                if ("Left".equals(category.categoryName())) id = HandObservation.LEFT;
                else if ("Right".equals(category.categoryName())) id = HandObservation.RIGHT;
                else continue;
                List<NormalizedLandmark> normalized = result.landmarks().get(hand);
                List<Landmark> world = result.worldLandmarks().get(hand);
                if (normalized.size() != 21 || world.size() != 21) continue;
                float[] model = new float[63], pixels = new float[42];
                for (int i = 0; i < 21; i++) {
                    Landmark p = world.get(i);
                    model[i*3] = p.x(); model[i*3+1] = p.y(); model[i*3+2] = p.z();
                    pixels[i*2] = normalized.get(i).x()*frame.width;
                    pixels[i*2+1] = normalized.get(i).y()*frame.height;
                }
                HandObservation observation = estimator.estimate(id, category.score(), model, pixels,
                        intrinsics, transform, frame.width, frame.height, scale);
                if (observation != null && (bySide[id] == null
                        || observation.confidence > bySide[id].confidence)) bySide[id] = observation;
            }
            ArrayList<HandObservation> hands = new ArrayList<>(2);
            for (HandObservation hand : bySide) if (hand != null) hands.add(hand);
            synchronized (lock) {
                if (!closed && generation == token) {
                    long age = SystemClock.elapsedRealtimeNanos() - captureElapsedNs;
                    listener.onHands(age < 0 || age > MAX_RESULT_AGE_NS ? Collections.emptyList()
                            : Collections.unmodifiableList(hands), captureElapsedNs);
                }
            }
        } catch (RuntimeException | LinkageError error) {
            synchronized (lock) {
                if (!closed && generation == token) {
                    failed = true;
                    listener.onError("Hand tracking unavailable: " + error.getMessage());
                    listener.onHands(Collections.emptyList(), captureElapsedNs);
                }
            }
        } finally {
            try {
                if (mpImage != null) mpImage.close();
            } finally {
                try {
                    if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();
                } finally {
                    synchronized (lock) { busy = false; }
                }
            }
        }
    }

    /** Manual metric calibration factor; 1.0 retains the model's learned scale. */
    public void setHandScale(float scale) {
        if (!Float.isFinite(scale) || scale < 0.5f || scale > 1.5f)
            throw new IllegalArgumentException("Hand scale must be 0.5..1.5");
        synchronized (lock) {
            if (closed) return;
            handScale = scale;
            generation++;
            listener.onHands(Collections.emptyList(), SystemClock.elapsedRealtimeNanos());
        }
    }

    /** Cancels publication of in-flight observations, e.g. on tracking loss or recenter. */
    public void invalidate() {
        synchronized (lock) {
            if (closed) return;
            generation++;
            listener.onHands(Collections.emptyList(), SystemClock.elapsedRealtimeNanos());
        }
    }

    @Override public void close() {
        synchronized (lock) {
            if (closed) return;
            closed = true;
            generation++;
            listener.onHands(Collections.emptyList(), SystemClock.elapsedRealtimeNanos());
            worker.execute(() -> {
                if (landmarker != null) { landmarker.close(); landmarker = null; }
            });
            worker.shutdown();
        }
    }

    private static final class YuvFrame {
        final int width, height, chromaWidth;
        final byte[] y, u, v;
        YuvFrame(int width, int height, byte[] y, byte[] u, byte[] v) {
            this.width = width; this.height = height; this.chromaWidth = (width+1)/2;
            this.y = y; this.u = u; this.v = v;
        }
        static YuvFrame copy(Image image) {
            int w = image.getWidth(), h = image.getHeight();
            Rect crop = image.getCropRect();
            if (image.getFormat() != ImageFormat.YUV_420_888 || w <= 0 || h <= 0
                    || w > 4096 || h > 4096 || crop.left != 0 || crop.top != 0
                    || crop.width() != w || crop.height() != h || image.getPlanes().length != 3)
                throw new IllegalArgumentException("Expected uncropped ARCore YUV_420_888 image");
            Image.Plane[] planes = image.getPlanes();
            return new YuvFrame(w, h, copyPlane(planes[0], w, h),
                    copyPlane(planes[1], (w+1)/2, (h+1)/2), copyPlane(planes[2], (w+1)/2, (h+1)/2));
        }
        static byte[] copyPlane(Image.Plane plane, int width, int height) {
            ByteBuffer buffer = plane.getBuffer().duplicate();
            int offset = buffer.position(), row = plane.getRowStride(), pixel = plane.getPixelStride();
            byte[] bytes = new byte[width*height];
            for (int y = 0; y < height; y++) for (int x = 0; x < width; x++)
                bytes[y*width+x] = buffer.get(offset+y*row+x*pixel);
            return bytes;
        }
        Bitmap toBitmap() {
            int[] rgba = new int[width*height];
            for (int row = 0; row < height; row++) for (int col = 0; col < width; col++) {
                int pos = row*width+col, uv = (row/2)*chromaWidth+col/2;
                int luminance = Math.max(0, (y[pos]&255)-16);
                int cb = (u[uv]&255)-128, cr = (v[uv]&255)-128;
                int r = clamp((298*luminance+409*cr+128)>>8);
                int g = clamp((298*luminance-100*cb-208*cr+128)>>8);
                int b = clamp((298*luminance+516*cb+128)>>8);
                rgba[pos] = 0xff000000 | r<<16 | g<<8 | b;
            }
            return Bitmap.createBitmap(rgba, width, height, Bitmap.Config.ARGB_8888);
        }
        static int clamp(int value) { return Math.max(0, Math.min(255, value)); }
    }
}
