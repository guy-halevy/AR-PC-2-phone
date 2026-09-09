package viritualisres.phonevr.xr;

/** Maps the unspecified AR frame clock into elapsedRealtime without claiming clock sync. */
public final class FrameClock {
    private long minimumOffset = Long.MAX_VALUE;
    private long previous = 0;
    public synchronized long map(long timestampNs, long arrivalElapsedNs) {
        if (timestampNs <= 0 || timestampNs <= previous) return 0;
        previous = timestampNs;
        long sample = arrivalElapsedNs - timestampNs;
        minimumOffset = Math.min(minimumOffset, sample);
        return Math.min(arrivalElapsedNs, timestampNs + minimumOffset);
    }
    public synchronized void reset() { minimumOffset=Long.MAX_VALUE; previous=0; }
}
