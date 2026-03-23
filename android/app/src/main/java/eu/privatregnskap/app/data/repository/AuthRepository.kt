package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.UserResponse
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

interface AuthRepository {
    val isLoggedIn: Flow<Boolean>
    suspend fun login(email: String, password: String): Result<UserResponse>
    suspend fun loginWithPasskey(optionsJson: String): Result<String>
    suspend fun verifyPasskeyLogin(credentialJson: String, optionsJson: String): Result<Unit>
    suspend fun requestPasswordReset(email: String): Result<Unit>
    suspend fun logout()
}

@Singleton
class AuthRepositoryImpl @Inject constructor(
    private val apiService: ApiService,
    private val tokenRepository: TokenRepository
) : AuthRepository {

    private val _isLoggedIn = MutableStateFlow(tokenRepository.isLoggedIn())
    override val isLoggedIn: Flow<Boolean> = _isLoggedIn.asStateFlow()

    override suspend fun login(email: String, password: String): Result<UserResponse> {
        return try {
            val token = apiService.login(email, password)
            tokenRepository.saveAccessToken(token.accessToken)
            val user = apiService.getMe()
            _isLoggedIn.value = true
            Result.success(user)
        } catch (e: Exception) {
            tokenRepository.clearTokens()
            Result.failure(e)
        }
    }

    override suspend fun loginWithPasskey(optionsJson: String): Result<String> {
        return try {
            val body = "{}".toRequestBody("application/json".toMediaType())
            val responseBody = apiService.passkeyLoginBegin(body)
            Result.success(responseBody.string())
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun verifyPasskeyLogin(credentialJson: String, optionsJson: String): Result<Unit> {
        return try {
            val assertionObj = JSONObject(credentialJson)
            val challengeKey = JSONObject(optionsJson).optString("challenge_key", "")
            if (challengeKey.isNotEmpty()) {
                assertionObj.put("challenge_key", challengeKey)
            }
            val rawId = assertionObj.optString("rawId").ifEmpty { assertionObj.optString("id") }
            val requestObj = JSONObject()
            requestObj.put("credential_id", rawId)
            requestObj.put("assertion", assertionObj)
            val body = requestObj.toString().toRequestBody("application/json".toMediaType())
            val token = apiService.passkeyLoginComplete(body)
            tokenRepository.saveAccessToken(token.accessToken)
            _isLoggedIn.value = true
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun requestPasswordReset(email: String): Result<Unit> {
        return try {
            apiService.requestPasswordReset(
                eu.privatregnskap.app.data.network.dto.PasswordResetRequest(email)
            )
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun logout() {
        tokenRepository.clearTokens()
        _isLoggedIn.value = false
    }
}
