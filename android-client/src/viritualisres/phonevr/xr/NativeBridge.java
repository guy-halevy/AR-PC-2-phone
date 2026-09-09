package viritualisres.phonevr.xr;

public final class NativeBridge {
    private NativeBridge() {}
    public static native void publishPose(boolean enabled, boolean tracking,
                                          long captureElapsedNs, float[] positionQuaternion);
    public static native boolean viewerConfigured();
}
