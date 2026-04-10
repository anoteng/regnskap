package eu.privatregnskap.app.data.repository

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.biometric.BiometricManager
import dagger.hilt.android.qualifiers.ApplicationContext
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

interface BiometricRepository {
    fun isBiometricAvailable(): Boolean
    fun isBiometricLoginEnabled(): Boolean
    fun getCipherForEncryption(): Cipher
    fun getCipherForDecryption(): Cipher?
    fun encryptAndStore(refreshToken: String, cipher: Cipher)
    fun decryptToken(cipher: Cipher): String?
    fun clearBiometricData()
}

@Singleton
class BiometricRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context
) : BiometricRepository {

    private val prefs by lazy {
        context.getSharedPreferences("biometric_prefs", Context.MODE_PRIVATE)
    }

    override fun isBiometricAvailable(): Boolean {
        val bm = BiometricManager.from(context)
        return bm.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) ==
                BiometricManager.BIOMETRIC_SUCCESS
    }

    override fun isBiometricLoginEnabled(): Boolean =
        prefs.getString(KEY_ENCRYPTED_TOKEN, null) != null

    override fun getCipherForEncryption(): Cipher {
        val key = getOrCreateKey()
        return Cipher.getInstance(TRANSFORMATION).apply {
            init(Cipher.ENCRYPT_MODE, key)
        }
    }

    override fun getCipherForDecryption(): Cipher? {
        val ivStr = prefs.getString(KEY_IV, null) ?: return null
        val iv = Base64.decode(ivStr, Base64.DEFAULT)
        return try {
            val key = getOrCreateKey()
            Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
            }
        } catch (e: KeyPermanentlyInvalidatedException) {
            // New biometrics enrolled — key is no longer valid
            clearBiometricData()
            null
        }
    }

    override fun encryptAndStore(refreshToken: String, cipher: Cipher) {
        val encrypted = cipher.doFinal(refreshToken.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString(KEY_ENCRYPTED_TOKEN, Base64.encodeToString(encrypted, Base64.DEFAULT))
            .putString(KEY_IV, Base64.encodeToString(cipher.iv, Base64.DEFAULT))
            .apply()
    }

    override fun decryptToken(cipher: Cipher): String? {
        val encStr = prefs.getString(KEY_ENCRYPTED_TOKEN, null) ?: return null
        val encrypted = Base64.decode(encStr, Base64.DEFAULT)
        return String(cipher.doFinal(encrypted), Charsets.UTF_8)
    }

    override fun clearBiometricData() {
        prefs.edit().remove(KEY_ENCRYPTED_TOKEN).remove(KEY_IV).apply()
        try {
            KeyStore.getInstance("AndroidKeyStore").apply {
                load(null)
                deleteEntry(KEY_ALIAS)
            }
        } catch (_: Exception) {}
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        keyStore.getKey(KEY_ALIAS, null)?.let { return it as SecretKey }

        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            .apply {
                init(
                    KeyGenParameterSpec.Builder(
                        KEY_ALIAS,
                        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                    )
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .setUserAuthenticationRequired(true)
                        .setInvalidatedByBiometricEnrollment(true)
                        .build()
                )
            }.generateKey()
    }

    companion object {
        private const val KEY_ALIAS = "biometric_refresh_key"
        private const val KEY_ENCRYPTED_TOKEN = "bio_enc_token"
        private const val KEY_IV = "bio_iv"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
