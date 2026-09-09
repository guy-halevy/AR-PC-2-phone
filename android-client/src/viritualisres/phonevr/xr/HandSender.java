package viritualisres.phonevr.xr;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.SystemClock;
import android.util.Base64;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONArray;
import org.json.JSONObject;

/** Latest-only encrypted derived-hand transport. No images or background retries. */
public final class HandSender implements AutoCloseable {
    private static final Object COUNTER_LOCK=new Object();
    private static final int B64=Base64.URL_SAFE|Base64.NO_PADDING|Base64.NO_WRAP;
    private final SharedPreferences prefs;
    private final String host, counterName;
    private final int port;
    private final byte[] key, session;
    private final AtomicReference<Pending> pending=new AtomicReference<>();
    private final Thread worker;
    private volatile boolean closed;
    private volatile String error="";
    private long next, limit;
    private static final class Pending {
        final List<HandObservation> hands;
        final long capture;
        Pending(List<HandObservation> h,long t){hands=new ArrayList<>(h);capture=t;}
    }
    public HandSender(Context context,String text) {
        try {
            if(text.length()>4096)throw new IllegalArgumentException("Pairing too large");
            Uri uri=Uri.parse(text);
            if(!"phonexr".equals(uri.getScheme())||!"pair".equals(uri.getHost()))throw new IllegalArgumentException("Use a PhoneXR pairing URI");
            JSONObject obj=new JSONObject(new String(Base64.decode(uri.getQueryParameter("data"),B64),StandardCharsets.UTF_8));
            if(obj.getInt("v")!=2)throw new IllegalArgumentException("Unsupported pairing version");
            host=obj.getString("host");port=obj.getInt("port");
            // Numeric LAN addresses avoid DNS lookup on the UI thread and DNS rebinding.
            if(!(host.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+") || (host.contains(":") && host.matches("[0-9a-fA-F:.]+")))||port<1024||port>65535)throw new IllegalArgumentException("Use a numeric LAN address and valid port");
            InetAddress address=InetAddress.getByName(host);
            if(!(address.isSiteLocalAddress()||address.isLinkLocalAddress()||address.isLoopbackAddress()))throw new IllegalArgumentException("Pair with a local-network PC");
            key=decode(obj,"key",32);session=decode(obj,"session",16);
            ByteBuffer identity=ByteBuffer.allocate(48).put(key).put(session);
            counterName="counter-"+Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(identity.array()),B64);
            prefs=context.getSharedPreferences("xr-counters",0);
        } catch(Exception e){throw new IllegalArgumentException("Invalid pairing: "+e.getMessage(),e);}
        worker=new Thread(this::run,"PhoneXR-HandSender");worker.start();
    }
    private static byte[] decode(JSONObject j,String field,int length)throws Exception{
        byte[] result=Base64.decode(j.getString(field),B64);
        if(result.length!=length)throw new IllegalArgumentException("Invalid "+field);
        return result;
    }
    private long sequence() {
        if(next==limit) synchronized(COUNTER_LOCK) {
            long start=prefs.getLong(counterName,0);
            if(start<0||start>Long.MAX_VALUE-1024)throw new IllegalStateException("Pair again: sequence exhausted");
            if(!prefs.edit().putLong(counterName,start+1024).commit())throw new IllegalStateException("Cannot reserve packet counters");
            next=start;limit=start+1024;
        }
        return next++;
    }
    public void send(List<HandObservation> hands,long capture){if(!closed)pending.set(new Pending(hands,capture));}
    public void pause(){send(Collections.emptyList(),SystemClock.elapsedRealtimeNanos());}
    public String destination(){return host+":"+port;}
    public String lastError(){return error;}
    public void close(){pending.set(new Pending(Collections.emptyList(),SystemClock.elapsedRealtimeNanos()));closed=true;}
    private void run(){
        try(DatagramSocket socket=new DatagramSocket()){
            InetAddress address=InetAddress.getByName(host);
            java.security.SecureRandom random=new java.security.SecureRandom();
            while(!closed||pending.get()!=null){
                Pending item=pending.getAndSet(null);
                if(item==null){Thread.sleep(10);continue;}
                long now=SystemClock.elapsedRealtimeNanos();
                double age=(now-item.capture)/1e6;
                List<HandObservation> hands=age>=0&&age<=150?item.hands:Collections.emptyList();
                JSONArray encoded=new JSONArray();
                for(HandObservation h:hands){
                    if(encoded.length()==2)break;
                    if(h.confidence<.65f||h.reprojectionErrorPx>8)continue;
                    JSONObject hand=new JSONObject();hand.put("id",h.id);hand.put("confidence",h.confidence);hand.put("reprojectionErrorPx",h.reprojectionErrorPx);
                    JSONArray points=new JSONArray();
                    for(int i=0;i<21;i++)points.put(new JSONArray().put(h.standingLandmarks[3*i]).put(h.standingLandmarks[3*i+1]).put(h.standingLandmarks[3*i+2]));
                    hand.put("landmarks",points);encoded.put(hand);
                }
                JSONObject payload=new JSONObject().put("ageMs",hands.isEmpty()?0:age).put("sentMonoMs",now/1e6).put("hands",encoded);
                long seq=sequence();
                byte[] nonce=new byte[12];random.nextBytes(nonce);
                byte[] header=ByteBuffer.allocate(40).put(new byte[]{'P','X','H','2'}).put(session).putLong(seq).put(nonce).array();
                Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));cipher.updateAAD(header);
                byte[] encrypted=cipher.doFinal(payload.toString().getBytes(StandardCharsets.UTF_8));
                byte[] packet=ByteBuffer.allocate(40+encrypted.length).put(header).put(encrypted).array();
                if(packet.length>8192)throw new IllegalStateException("Hand packet too large");
                socket.send(new DatagramPacket(packet,packet.length,address,port));
            }
        }catch(Exception e){error=e.getClass().getSimpleName()+": "+e.getMessage();closed=true;pending.set(null);}
    }
}
