package eu.privatregnskap.app.data.network

import com.squareup.moshi.Moshi
import eu.privatregnskap.app.BuildConfig
import eu.privatregnskap.app.data.repository.TokenRepository
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import javax.inject.Inject

// On 401: attempts token refresh before clearing tokens and forcing logout
class UnauthorizedInterceptor @Inject constructor(
    private val tokenRepository: TokenRepository
) : Interceptor {

    // Bare client with no interceptors — used only for the refresh call
    private val refreshClient by lazy { OkHttpClient() }

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val response = chain.proceed(originalRequest)

        if (response.code != 401) return response

        // Don't retry the refresh endpoint itself
        if (originalRequest.url.encodedPath.contains("/auth/refresh")) {
            tokenRepository.clearTokens()
            return response
        }

        val refreshToken = tokenRepository.getRefreshToken()
        if (refreshToken == null) {
            tokenRepository.clearTokens()
            return response
        }

        // Attempt refresh
        val newAccessToken = tryRefresh(refreshToken) ?: run {
            tokenRepository.clearTokens()
            return response
        }

        tokenRepository.saveAccessToken(newAccessToken)
        response.close()

        // Retry original request with new token
        val retryRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer $newAccessToken")
            .build()
        return chain.proceed(retryRequest)
    }

    private fun tryRefresh(refreshToken: String): String? {
        return try {
            val body = JSONObject().apply { put("refresh_token", refreshToken) }
                .toString()
                .toRequestBody("application/json".toMediaType())

            val request = Request.Builder()
                .url("${BuildConfig.BASE_URL}auth/refresh")
                .post(body)
                .build()

            val resp = refreshClient.newCall(request).execute()
            if (!resp.isSuccessful) return null

            val json = JSONObject(resp.body?.string() ?: return null)
            json.optString("access_token").takeIf { it.isNotEmpty() }
        } catch (e: Exception) {
            null
        }
    }
}
