package viritualisres.phonevr.xr;

/** One frame of estimated hand geometry in calibrated standing space (meters).
 * Handedness IDs are semantic, not indices in MediaPipe's changing result order.
 * Confidence is the handedness classifier score, not metric depth accuracy.
 */
public final class HandObservation {
    public static final int LEFT = 0;
    public static final int RIGHT = 1;
    public final int handednessId;
    public final float confidence;
    public final float[] standingLandmarks;
    public final float reprojectionErrorPixels;
    public final float reprojectionErrorPx;
    public final String id;

    public HandObservation(int handednessId, float confidence, float[] landmarks,
                           float reprojectionErrorPixels) {
        if (landmarks.length != 63) throw new IllegalArgumentException("Expected 21 XYZ landmarks");
        this.handednessId = handednessId;
        this.id = handednessId == LEFT ? "left" : "right";
        this.confidence = confidence;
        this.standingLandmarks = landmarks.clone();
        this.reprojectionErrorPixels = reprojectionErrorPixels;
        this.reprojectionErrorPx = reprojectionErrorPixels;
    }

    public float[] indexTip() { return landmark(8); }
    public float[] thumbTip() { return landmark(4); }
    public float[] landmark(int index) {
        if (index < 0 || index >= 21) throw new IllegalArgumentException("Landmark index");
        int p = index * 3;
        return new float[] {standingLandmarks[p], standingLandmarks[p + 1], standingLandmarks[p + 2]};
    }
}
