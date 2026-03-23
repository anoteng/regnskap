package eu.privatregnskap.app.data.network

import eu.privatregnskap.app.data.repository.TokenRepository
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

// Clears tokens on 401 so NavGraph redirects to login
class UnauthorizedInterceptor @Inject constructor(
    private val tokenRepository: TokenRepository
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (response.code == 401) {
            tokenRepository.clearTokens()
        }
        return response
    }
}
