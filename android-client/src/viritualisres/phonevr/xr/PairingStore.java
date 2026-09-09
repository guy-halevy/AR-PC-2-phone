package viritualisres.phonevr.xr;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Pairing secrets stay in app-private storage encrypted by an Android Keystore key. */
public final class PairingStore {
    private static final String ALIAS="phonexr.pairing.v1";
    private static SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator=KeyGenerator.getInstance("AES", "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
            generator.generateKey();
        }
        return (SecretKey)store.getKey(ALIAS,null);
    }
    public static synchronized void save(Context context,String uri) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,key());
        byte[] encrypted=cipher.doFinal(uri.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        byte[] combined=new byte[12+encrypted.length];
        System.arraycopy(cipher.getIV(),0,combined,0,12);
        System.arraycopy(encrypted,0,combined,12,encrypted.length);
        if (!context.getSharedPreferences("xr-private",0).edit().putString("pairing",
             Base64.encodeToString(combined,Base64.NO_WRAP)).commit()) throw new IllegalStateException("Pairing save failed");
    }
    public static synchronized String load(Context context) throws Exception {
        String text=context.getSharedPreferences("xr-private",0).getString("pairing",null);
        if (text==null) return null;
        byte[] data=Base64.decode(text,Base64.NO_WRAP);
        if(data.length<28) throw new IllegalStateException("Invalid saved pairing");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Arrays.copyOf(data,12)));
        return new String(cipher.doFinal(data,12,data.length-12),java.nio.charset.StandardCharsets.UTF_8);
    }
}
