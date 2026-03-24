package eu.privatregnskap.app.data.repository

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

interface TokenRepository {
    val isLoggedInFlow: Flow<Boolean>
    fun saveAccessToken(accessToken: String)
    fun getAccessToken(): String?
    fun clearTokens()
    fun isLoggedIn(): Boolean
}

@Singleton
class TokenRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context
) : TokenRepository {

    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            context,
            "privatregnskap_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    private val _isLoggedInFlow = MutableStateFlow(isLoggedIn())
    override val isLoggedInFlow: Flow<Boolean> = _isLoggedInFlow.asStateFlow()

    override fun saveAccessToken(accessToken: String) {
        prefs.edit().putString(KEY_ACCESS_TOKEN, accessToken).apply()
        _isLoggedInFlow.value = true
    }

    override fun getAccessToken(): String? = prefs.getString(KEY_ACCESS_TOKEN, null)

    override fun clearTokens() {
        prefs.edit().remove(KEY_ACCESS_TOKEN).apply()
        _isLoggedInFlow.value = false
    }

    override fun isLoggedIn(): Boolean = getAccessToken() != null

    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
    }
}
