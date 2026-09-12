package viritualisres.phonevr.xr;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.Image;
import android.opengl.GLES11Ext;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.SystemClock;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ScrollView;
import androidx.core.app.ActivityCompat;
import com.google.ar.core.Anchor;
import com.google.ar.core.ArCoreApk;
import com.google.ar.core.Camera;
import com.google.ar.core.CameraIntrinsics;
import com.google.ar.core.Config;
import com.google.ar.core.Frame;
import com.google.ar.core.Pose;
import com.google.ar.core.Session;
import com.google.ar.core.TrackingState;
import com.google.ar.core.exceptions.NotYetAvailableException;
import java.util.Collections;
import java.util.List;

/** ARCore is the only camera owner; inference uses its timestamp-matched CPU image. */
public final class XrController implements HandTracker.Listener {
    public static final int CAMERA_PERMISSION=731;
    private final Activity activity;
    private final SharedPreferences prefs;
    private final Object sessionLock=new Object();
    private final FrameClock clock=new FrameClock();
    private final HandTracker hands;
    private final TextView label;
    private volatile HandSender sender;
    private volatile boolean recenter=true, enabled, handsEnabled, showHands, paused=true;
    private volatile float eyeHeight, offsetX, offsetY, offsetZ;
    private volatile String lastStatus="";
    private Session session;
    private Anchor anchor;
    private boolean resumed, installRequested;
    private int texture, width=1, height=1;
    private boolean textureChanged=true;
    private long lastHandFrame;

    public XrController(Activity activity,GLSurfaceView surface){
        this.activity=activity;prefs=activity.getSharedPreferences("xr-settings",0);
        enabled=prefs.getBoolean("enabled",true);handsEnabled=prefs.getBoolean("hands",true);showHands=prefs.getBoolean("showHands",true);
        eyeHeight=prefs.getFloat("height",1.6f);offsetX=prefs.getFloat("offsetX",0);
        offsetY=prefs.getFloat("offsetY",0);offsetZ=prefs.getFloat("offsetZ",.04f);
        hands=new HandTracker(activity,this);hands.setHandScale(prefs.getFloat("handScale",1));
        LinearLayout controls=new LinearLayout(activity);controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER_VERTICAL);controls.setPadding(12,4,12,4);controls.setBackgroundColor(0xc018202c);
        label=new TextView(activity);label.setTextColor(0xffeef5ff);label.setTextSize(12);label.setText("PhoneXR · preparing");
        controls.addView(label,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        Button settings=new Button(activity);settings.setText("PhoneXR setup");settings.setOnClickListener(v->settings());controls.addView(settings);
        activity.addContentView(controls,new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));
        try{String saved=PairingStore.load(activity);if(saved!=null)sender=new HandSender(activity,saved);}catch(Exception e){status("Pairing unavailable; open setup");}
    }
    private void status(String text){if(text.equals(lastStatus))return;lastStatus=text;activity.runOnUiThread(()->label.setText("PhoneXR · "+text));}
    public void onResume(){
        paused=false;
        NativeBridge.publishPose(false,false,0,null);
        if(!enabled){NativeBridge.publishPose(false,false,0,null);status("rotation only · AR disabled");return;}
        if(!NativeBridge.viewerConfigured()){status("complete Cardboard viewer setup first");return;}
        if(ActivityCompat.checkSelfPermission(activity,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){
            ActivityCompat.requestPermissions(activity,new String[]{Manifest.permission.CAMERA},CAMERA_PERMISSION);status("camera permission required");return;
        }
        synchronized(sessionLock){
            try{
                if(session==null){
                    ArCoreApk.Availability availability=ArCoreApk.getInstance().checkAvailability(activity);
                    if(availability.isUnsupported()){status("AR unavailable on this device · rotation only");return;}
                    if(ArCoreApk.getInstance().requestInstall(activity,!installRequested)==ArCoreApk.InstallStatus.INSTALL_REQUESTED){installRequested=true;return;}
                    session=new Session(activity);
                    Config config=new Config(session);config.setFocusMode(Config.FocusMode.AUTO);
                    config.setPlaneFindingMode(Config.PlaneFindingMode.DISABLED);
                    config.setUpdateMode(Config.UpdateMode.LATEST_CAMERA_IMAGE);
                    session.configure(config);recenter=true;clock.reset();textureChanged=true;
                }
                if(!resumed){session.resume();resumed=true;}
                NativeBridge.publishPose(true,false,0,null);status("finding tracking features");
            }catch(Exception e){status("AR unavailable: "+e.getClass().getSimpleName());NativeBridge.publishPose(false,false,0,null);}
        }
    }
    public void beforePause(){paused=true;hands.invalidate();NativeBridge.publishHands(0,null);HandSender s=sender;if(s!=null)s.pause();NativeBridge.publishPose(enabled,false,0,null);}
    // Called after GLSurfaceView.onPause, so no GL frame is waiting for the UI thread.
    public void afterPause(){synchronized(sessionLock){if(session!=null&&resumed){session.pause();resumed=false;}}}
    public void onDestroy(){beforePause();afterPause();hands.close();HandSender s=sender;if(s!=null)s.close();synchronized(sessionLock){if(anchor!=null){anchor.detach();anchor=null;}if(session!=null){session.close();session=null;}}}
    public void onPermissionResult(){if(!paused)onResume();}
    public void surfaceCreated(){
        int[] names=new int[1],previous=new int[1];
        GLES20.glGetIntegerv(GLES11Ext.GL_TEXTURE_BINDING_EXTERNAL_OES,previous,0);
        GLES20.glGenTextures(1,names,0);texture=names[0];
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,texture);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,previous[0]);textureChanged=true;
    }
    public void surfaceChanged(int w,int h){width=w;height=h;}
    public void onFrame(){
        if(paused||!enabled)return;
        synchronized(sessionLock){
            if(session==null||!resumed||texture==0)return;
            try{
                if(textureChanged){session.setCameraTextureName(texture);textureChanged=false;}
                session.setDisplayGeometry(activity.getWindowManager().getDefaultDisplay().getRotation(),width,height);
                Frame frame=session.update();Camera camera=frame.getCamera();
                if(camera.getTrackingState()!=TrackingState.TRACKING){lost("tracking paused: "+camera.getTrackingFailureReason());return;}
                long capture=clock.map(frame.getTimestamp(),SystemClock.elapsedRealtimeNanos());
                if(capture==0)return;
                Pose physical=camera.getPose();
                Pose mountedRotation=physical.inverse().compose(camera.getDisplayOrientedPose()).extractRotation();
                Pose cameraToHead=new Pose(new float[]{offsetX,offsetY,offsetZ},mountedRotation.getRotationQuaternion());
                Pose worldHead=physical.compose(cameraToHead);
                if(recenter||anchor==null){
                    hands.invalidate();NativeBridge.publishHands(0,null);HandSender s=sender;if(s!=null)s.pause();
                    if(anchor!=null)anchor.detach();
                    float[] f=worldHead.rotateVector(new float[]{0,0,-1});
                    float yaw=(float)Math.atan2(-f[0],-f[2]);
                    anchor=session.createAnchor(new Pose(worldHead.getTranslation(),new float[]{0,(float)Math.sin(yaw/2),0,(float)Math.cos(yaw/2)}));
                    recenter=false;
                }
                if(anchor.getTrackingState()!=TrackingState.TRACKING){lost("origin tracking paused");return;}
                Pose standingCamera=Pose.makeTranslation(0,eyeHeight,0).compose(anchor.getPose().inverse()).compose(physical);
                Pose standingHead=standingCamera.compose(cameraToHead);
                float[] t=standingHead.getTranslation(),q=standingHead.getRotationQuaternion();
                NativeBridge.publishPose(true,true,capture,new float[]{t[0],t[1],t[2],q[0],q[1],q[2],q[3]});
                HandSender s=sender;
                status("AR tracking · "+(s==null?"pair PC in setup":s.lastError().isEmpty()?s.destination():s.lastError()));
                if(handsEnabled&&capture-lastHandFrame>=33000000L){
                    lastHandFrame=capture;
                    try{
                        Image image=frame.acquireCameraImage();
                        if(image.getTimestamp()!=frame.getTimestamp()){image.close();return;}
                        CameraIntrinsics intrinsics=camera.getImageIntrinsics();float[] focal=intrinsics.getFocalLength(),center=intrinsics.getPrincipalPoint();
                        float[] transform=new float[16];standingCamera.toMatrix(transform,0);
                        if(!hands.submit(image,new float[]{focal[0],focal[1],center[0],center[1]},transform,capture))image.close();
                    }catch(NotYetAvailableException ignored){ /* Next frame; no queue of camera images. */ }
                }
            }catch(Exception e){lost("tracking error: "+e.getClass().getSimpleName());}
        }
    }
    private void lost(String reason){NativeBridge.publishPose(true,false,0,null);hands.invalidate();NativeBridge.publishHands(0,null);HandSender s=sender;if(s!=null)s.pause();status(reason);}
    public void onHands(List<HandObservation> result,long capture){
        boolean active=!paused&&enabled&&handsEnabled;
        if(active&&showHands&&!result.isEmpty()){
            int count=Math.min(2,result.size());float[] points=new float[count*63];
            for(int i=0;i<count;i++)System.arraycopy(result.get(i).standingLandmarks,0,points,i*63,63);
            NativeBridge.publishHands(capture,points);
        }else NativeBridge.publishHands(0,null);
        HandSender s=sender;if(s!=null)s.send(active?result:Collections.emptyList(),capture);
    }
    public void onError(String message){NativeBridge.publishHands(0,null);status(message);}
    private EditText field(LinearLayout layout,String title,String value){TextView hint=new TextView(activity);hint.setText(title);layout.addView(hint);EditText edit=new EditText(activity);edit.setText(value);edit.setSingleLine(true);layout.addView(edit);return edit;}
    private void settings(){
        LinearLayout box=new LinearLayout(activity);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(24,8,24,8);
        CheckBox ar=new CheckBox(activity);ar.setText("AR head tracking");ar.setChecked(enabled);box.addView(ar);
        CheckBox hand=new CheckBox(activity);hand.setText("Local hand tracking");hand.setChecked(handsEnabled);box.addView(hand);
        CheckBox visible=new CheckBox(activity);visible.setText("Show hand skeleton in both eyes");visible.setChecked(showHands);box.addView(visible);
        EditText pair=field(box,"PC pairing URI (leave empty to keep current pairing)","");pair.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        EditText heightField=field(box,"Standing eye height in meters",Float.toString(eyeHeight));
        EditText offsets=field(box,"Camera → eye offset in meters: x,y,z",offsetX+","+offsetY+","+offsetZ);
        EditText scale=field(box,"Hand depth calibration scale (0.5–1.5)",Float.toString(prefs.getFloat("handScale",1)));
        TextView note=new TextView(activity);note.setText("Frames stay on this phone. Hand depth is estimated; calibrate before enabling PC input. Recenter while facing your intended forward direction. AR uses Google Play Services for AR.");box.addView(note);
        ScrollView scroll=new ScrollView(activity);scroll.addView(box);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("PhoneXR setup").setView(scroll).setNegativeButton("Cancel",null).setNeutralButton("Recenter",(d,w)->{recenter=true;hands.invalidate();NativeBridge.publishHands(0,null);HandSender s=sender;if(s!=null)s.pause();}).setPositiveButton("Apply",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{
                float h=Float.parseFloat(heightField.getText().toString());String[] xyz=offsets.getText().toString().split(",");
                if(xyz.length!=3||!Float.isFinite(h)||h<.3f||h>2.5f)throw new IllegalArgumentException("Check height and offset");
                float[] o=new float[3];for(int i=0;i<3;i++){o[i]=Float.parseFloat(xyz[i].trim());if(!Float.isFinite(o[i])||Math.abs(o[i])>.3f)throw new IllegalArgumentException("Offset must be within 0.3 meters");}
                float hs=Float.parseFloat(scale.getText().toString());if(!Float.isFinite(hs)||hs<.5f||hs>1.5f)throw new IllegalArgumentException("Hand scale must be 0.5–1.5");
                String uri=pair.getText().toString().trim();
                if(!uri.isEmpty()){HandSender replacement=new HandSender(activity,uri);try{PairingStore.save(activity,uri);}catch(Exception e){replacement.close();throw e;}HandSender old=sender;sender=replacement;if(old!=null)old.close();}
                beforePause();afterPause();enabled=ar.isChecked();handsEnabled=hand.isChecked();showHands=visible.isChecked();eyeHeight=h;offsetX=o[0];offsetY=o[1];offsetZ=o[2];hands.setHandScale(hs);recenter=true;
                prefs.edit().putBoolean("enabled",enabled).putBoolean("hands",handsEnabled).putBoolean("showHands",showHands).putFloat("height",h).putFloat("offsetX",o[0]).putFloat("offsetY",o[1]).putFloat("offsetZ",o[2]).putFloat("handScale",hs).apply();
                dialog.dismiss();onResume();
            }catch(Exception e){pair.setError(e.getMessage());}
        }));dialog.show();
    }
}
