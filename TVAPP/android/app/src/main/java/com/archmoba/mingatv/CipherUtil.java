package com.archmoba.mingatv;

import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Decodifica tokens encv1: compatibles con generador_cifrado_minga_tv.py.
 *
 * Formato:
 *   encv1:BASE64_URLSAFE(salt[16] || ASCII(FERNET_TOKEN))
 * Derivacion: PBKDF2-HMAC-SHA256, 390000 iteraciones, 32 bytes
 * Fernet: HMAC-SHA256 (primera mitad) + AES-128-CBC/PKCS7 (segunda mitad)
 *
 * AVISO: la guia embebida NO protege contra ingenieria inversa del APK.
 */
final class CipherUtil {
    private static final String PREFIX = "encv1:";
    private static final String GUIDE = "dfdfdfhbe645293858654764t3ui48936274098";
    private static final int ITERATIONS = 390_000;
    private static final int SALT_BYTES = 16;
    private static final int MAC_BYTES = 32;

    private CipherUtil() {}

    static String decrypt(String value) throws GeneralSecurityException {
        if (value == null) {
            return "";
        }
        if (!value.startsWith(PREFIX)) {
            return value;
        }

        byte[] packet;
        try {
            packet = Base64.decode(value.substring(PREFIX.length()), Base64.URL_SAFE | Base64.NO_WRAP);
        } catch (IllegalArgumentException e) {
            throw new GeneralSecurityException("Datos cifrados invalidos.");
        }
        if (packet.length <= SALT_BYTES) {
            throw new GeneralSecurityException("Token cifrado incompleto.");
        }
        byte[] salt = Arrays.copyOfRange(packet, 0, SALT_BYTES);
        String tokenText = new String(packet, SALT_BYTES, packet.length - SALT_BYTES,
                StandardCharsets.US_ASCII);
        byte[] token;
        try {
            token = Base64.decode(tokenText, Base64.URL_SAFE | Base64.NO_WRAP);
        } catch (IllegalArgumentException e) {
            throw new GeneralSecurityException("Formato Fernet invalido.");
        }
        if (token.length < 1 + 8 + 16 + 16 + MAC_BYTES || (token[0] & 0xff) != 0x80) {
            throw new GeneralSecurityException("Version Fernet incorrecta.");
        }
        int cipherLength = token.length - (1 + 8 + 16 + MAC_BYTES);
        if (cipherLength <= 0 || cipherLength % 16 != 0) {
            throw new GeneralSecurityException("Longitud cifrada incorrecta.");
        }

        PBEKeySpec spec = new PBEKeySpec(GUIDE.toCharArray(), salt, ITERATIONS, 256);
        byte[] key;
        try {
            key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
                    .generateSecret(spec).getEncoded();
        } finally {
            spec.clearPassword();
        }
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, 0, 16, "HmacSHA256"));
            mac.update(token, 0, token.length - MAC_BYTES);
            byte[] actualTag = mac.doFinal();
            byte[] expectedTag = Arrays.copyOfRange(token, token.length - MAC_BYTES, token.length);
            if (!MessageDigest.isEqual(actualTag, expectedTag)) {
                throw new GeneralSecurityException("Token alterado o guia incorrecta.");
            }
            byte[] iv = Arrays.copyOfRange(token, 9, 25);
            Cipher aes = Cipher.getInstance("AES/CBC/PKCS5Padding");
            aes.init(Cipher.DECRYPT_MODE,
                    new SecretKeySpec(key, 16, 16, "AES"), new IvParameterSpec(iv));
            byte[] plain = aes.doFinal(token, 25, cipherLength);
            return new String(plain, StandardCharsets.UTF_8);
        } finally {
            Arrays.fill(key, (byte) 0);
        }
    }
}
