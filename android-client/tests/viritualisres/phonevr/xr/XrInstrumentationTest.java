package viritualisres.phonevr.xr;

import static org.junit.Assert.*;
import android.content.Context;
import android.graphics.Bitmap;
import android.os.SystemClock;
import android.util.Base64;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.vision.core.RunningMode;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Collections;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.opencv.core.Core;

@RunWith(AndroidJUnit4.class)
public class XrInstrumentationTest {
    private Context context(){return InstrumentationRegistry.getInstrumentation().getTargetContext();}
    @Test public void syntheticPnPRecoversStandingGeometryAndRejectsBadCalibration(){
        System.loadLibrary(Core.NATIVE_LIBRARY_NAME);
        float[] model=new float[63],pixels=new float[42];
        float[] k={800,800,320,240},matrix={1,0,0,0,0,1,0,0,0,0,1,0,1,1.6f,2,1};
        for(int i=0;i<21;i++){
            float x=(i%5)*.02f,y=(i/5)*.025f,z=(float)Math.sin(i)*.008f;
            model[3*i]=x;model[3*i+1]=y;model[3*i+2]=z;
            pixels[2*i]=800*(x+.015f)/(z+.55f)+320;
            pixels[2*i+1]=800*(y-.04f)/(z+.55f)+240;
        }
        HandPoseEstimator estimator=new HandPoseEstimator();
        HandObservation result=estimator.estimate(0,.9f,model,pixels,k,matrix,640,480,1);
        assertNotNull(result);assertTrue(result.reprojectionErrorPx<.05);
        for(int i=0;i<21;i++){
            assertEquals(1+model[3*i]+.015f,result.standingLandmarks[3*i],.001);
            assertEquals(1.6f-model[3*i+1]+.04f,result.standingLandmarks[3*i+1],.001);
            assertEquals(2-model[3*i+2]-.55f,result.standingLandmarks[3*i+2],.001);
        }
        matrix[0]=-1;
        assertNull(estimator.estimate(0,.9f,model,pixels,k,matrix,640,480,1));
        matrix[0]=1;pixels[3]=Float.NaN;
        assertNull(estimator.estimate(0,.9f,model,pixels,k,matrix,640,480,1));
    }
    @Test public void bundledHandModelLoadsAndBlankFrameHasNoHands(){
        BaseOptions base=BaseOptions.builder().setModelAssetPath("hand_landmarker.task").build();
        HandLandmarker.HandLandmarkerOptions options=HandLandmarker.HandLandmarkerOptions.builder()
            .setBaseOptions(base).setRunningMode(RunningMode.IMAGE).setNumHands(2).build();
        Bitmap bitmap=Bitmap.createBitmap(640,480,Bitmap.Config.ARGB_8888);
        MPImage image=new BitmapImageBuilder(bitmap).build();
        try(HandLandmarker tracker=HandLandmarker.createFromOptions(context(),options)){
            assertTrue(tracker.detect(image).landmarks().isEmpty());
        }finally{image.close();bitmap.recycle();}
    }
    private String b64(byte[] bytes){return Base64.encodeToString(bytes,Base64.URL_SAFE|Base64.NO_PADDING|Base64.NO_WRAP);}
    @Test public void senderEncryptsAndReservesNewSequenceRangeAcrossInstances() throws Exception {
        byte[] key=new byte[32],session=new byte[16];
        SecureRandom random=new SecureRandom();random.nextBytes(key);random.nextBytes(session);
        try(DatagramSocket socket=new DatagramSocket(0,InetAddress.getByName("127.0.0.1"))){
            socket.setSoTimeout(5000);
            JSONObject fields=new JSONObject().put("v",2).put("host","127.0.0.1").put("port",socket.getLocalPort())
                .put("key",b64(key)).put("session",b64(session));
            String uri="phonexr://pair?data="+b64(fields.toString().getBytes(StandardCharsets.UTF_8));
            PairingStore.save(context(),uri);assertEquals(uri,PairingStore.load(context()));
            long previous=-1;
            for(int i=0;i<2;i++){
                HandSender sender=new HandSender(context(),uri);
                try{
                    sender.send(Collections.emptyList(),SystemClock.elapsedRealtimeNanos());
                    byte[] bytes=new byte[8192];DatagramPacket packet=new DatagramPacket(bytes,bytes.length);
                    long sequence;int length;
                    do{packet.setLength(bytes.length);socket.receive(packet);length=packet.getLength();sequence=ByteBuffer.wrap(bytes,20,8).getLong();}while(i>0&&sequence<1024);
                    assertTrue(sequence>previous);previous=sequence;
                    assertArrayEquals(session,Arrays.copyOfRange(bytes,4,20));
                    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
                    byte[] nonce=Arrays.copyOfRange(bytes,28,40);
                    cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));
                    cipher.updateAAD(bytes,0,40);
                    JSONObject decoded=new JSONObject(new String(cipher.doFinal(bytes,40,length-40),StandardCharsets.UTF_8));
                    assertEquals(0,decoded.getJSONArray("hands").length());
                    assertTrue(decoded.getDouble("ageMs")>=0);
                    bytes[length-1]^=1;
                    cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));cipher.updateAAD(bytes,0,40);
                    try{cipher.doFinal(bytes,40,length-40);fail("Tampered packet authenticated");}catch(javax.crypto.AEADBadTagException expected){}
                }finally{sender.close();}
            }
        }
    }
    @Test public void frameClockRejectsRepeatedFramesAndKeepsArrivalBound(){
        FrameClock clock=new FrameClock();assertEquals(5000,clock.map(1000,5000));
        assertEquals(0,clock.map(1000,5001));assertEquals(6000,clock.map(2000,6200));
        clock.reset();assertEquals(9000,clock.map(10,9000));
    }
}
