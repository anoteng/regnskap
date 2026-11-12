package eu.privatregnskap.app.data.bank

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.FormBody
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.time.LocalDate
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/** The bank answered, and the answer was no. Network trouble stays an IOException. */
class Sb1HttpException(val status: Int, val error: String?, detail: String) : Exception(detail)

/** optString turns a JSON null into the text "null"; this does not. */
internal fun JSONObject.text(key: String): String = if (isNull(key)) "" else optString(key)

data class Sb1Tokens(
    val accessToken: String,
    val expiresInSeconds: Long,
    val refreshToken: String?
)

data class Sb1Account(
    val key: String,
    val accountNumber: String,
    val name: String,
    val type: String
)

/**
 * SpareBank 1's API for personal clients, as measured against the bank in
 * November 2026.
 *
 * Has its own HTTP client on purpose. The app's client adds the Privatregnskap
 * login to every request it sends, and that has no business at the bank.
 */
@Singleton
class Sb1Api @Inject constructor() {

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    fun authorizeUrl(clientId: String, state: String): String =
        "$API_BASE/oauth/authorize".toHttpUrl().newBuilder()
            .addQueryParameter("client_id", clientId)
            .addQueryParameter("state", state)
            .addQueryParameter("redirect_uri", REDIRECT_URI)
            .addQueryParameter("response_type", "code")
            .build()
            .toString()

    suspend fun exchangeCode(clientId: String, clientSecret: String, code: String, state: String): Sb1Tokens =
        token(
            FormBody.Builder()
                .add("client_id", clientId)
                .add("client_secret", clientSecret)
                .add("grant_type", "authorization_code")
                .add("code", code)
                .add("state", state)
                .add("redirect_uri", REDIRECT_URI)
                .build()
        )

    suspend fun refresh(clientId: String, clientSecret: String, refreshToken: String): Sb1Tokens =
        token(
            FormBody.Builder()
                .add("client_id", clientId)
                .add("client_secret", clientSecret)
                .add("grant_type", "refresh_token")
                .add("refresh_token", refreshToken)
                .build()
        )

    private suspend fun token(form: FormBody): Sb1Tokens = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$API_BASE/oauth/token").post(form).build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw failure(response.code, body)
            val json = JSONObject(body)
            Sb1Tokens(
                accessToken = json.getString("access_token"),
                expiresInSeconds = json.optLong("expires_in", 600L),
                refreshToken = json.text("refresh_token").takeIf { it.isNotBlank() }
            )
        }
    }

    suspend fun accounts(accessToken: String): List<Sb1Account> {
        val json = get(accessToken, "$API_BASE/personal/banking/accounts".toHttpUrl())
        val array = json.optJSONArray("accounts") ?: return emptyList()
        return (0 until array.length()).mapNotNull { i ->
            val o = array.optJSONObject(i) ?: return@mapNotNull null
            val key = o.text("key")
            val number = o.text("accountNumber")
            if (key.isBlank() || number.isBlank()) return@mapNotNull null
            Sb1Account(
                key = key,
                accountNumber = number,
                name = o.text("name").ifBlank { number },
                type = o.text("type")
            )
        }
    }

    /** Every transaction on the account between the two dates, pending ones included. */
    suspend fun transactions(
        accessToken: String,
        accountKey: String,
        from: LocalDate,
        to: LocalDate
    ): List<JSONObject> {
        val url = "$API_BASE/personal/banking/transactions".toHttpUrl().newBuilder()
            .addQueryParameter("accountKey", accountKey)
            .addQueryParameter("fromDate", from.toString())
            .addQueryParameter("toDate", to.toString())
            .build()
        val json = get(accessToken, url)

        // A partial answer must not pass for a complete one: the next sync
        // starts where this one says it ended
        val errors = json.optJSONArray("errors")
        if (errors != null && errors.length() > 0) {
            throw Sb1HttpException(200, "partial", "Banken ga et ufullstendig svar: ${errors.opt(0).toString().take(200)}")
        }

        val array = json.optJSONArray("transactions") ?: return emptyList()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
    }

    private suspend fun get(accessToken: String, url: HttpUrl): JSONObject = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $accessToken")
            .header("Accept", ACCEPT)
            .build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw failure(response.code, body)
            JSONObject(body)
        }
    }

    /** Keeps the bank's error code and a short description, never the whole body. */
    private fun failure(status: Int, body: String): Sb1HttpException {
        val json = runCatching { JSONObject(body) }.getOrNull()
        val error = json?.text("error")?.takeIf { it.isNotBlank() }
        val description = json?.text("error_description")?.takeIf { it.isNotBlank() }
            ?: json?.text("message")?.takeIf { it.isNotBlank() }
        val detail = listOfNotNull(error, description).joinToString(": ").take(300)
        return Sb1HttpException(status, error, "Banken svarte $status" + if (detail.isBlank()) "" else " ($detail)")
    }

    companion object {
        const val API_BASE = "https://api.sparebank1.no"

        /** Must be registered on the client at the bank, letter for letter. */
        const val REDIRECT_URI = "http://localhost:8765/callback"
        const val REDIRECT_PORT = 8765
        const val REDIRECT_PATH = "/callback"

        private const val ACCEPT = "application/vnd.sparebank1.v1+json; charset=utf-8"
    }
}
