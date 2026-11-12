package eu.privatregnskap.app.data.bank

import android.content.Context
import android.net.Uri
import android.util.Base64
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.qualifiers.ApplicationContext
import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.BankAccountResponse
import eu.privatregnskap.app.data.network.dto.PushConnectionCreateRequest
import eu.privatregnskap.app.data.network.dto.PushConnectionResponse
import eu.privatregnskap.app.data.repository.TokenRepository
import eu.privatregnskap.app.worker.BankSyncWorker
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import retrofit2.HttpException
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.SecureRandom
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

sealed class SyncOutcome {
    /** Nothing is set up, or nobody is logged in: there was nothing to do. */
    object Idle : SyncOutcome()

    data class Done(val imported: Int, val message: String) : SyncOutcome()

    /** The bank stopped accepting the login during this run; only BankID helps. */
    object NeedsLogin : SyncOutcome()

    data class Failed(val message: String, val retryable: Boolean) : SyncOutcome()
}

/** The bank will not renew the login. */
class NeedsLoginException : Exception("Innloggingen i banken er utløpt. Logg inn med BankID på nytt.")

/** Something the user can act on, already worded for them. */
class BankSyncException(message: String) : Exception(message)

/** Backend errors arrive as {"detail": "..."} and are already in Norwegian. */
fun Throwable.bankSyncMessage(): String = when (this) {
    is HttpException -> {
        val detail = runCatching {
            response()?.errorBody()?.string()?.let { JSONObject(it).optString("detail") }
        }.getOrNull()
        if (!detail.isNullOrBlank()) detail else "Privatregnskap svarte ${code()}"
    }
    is IOException -> "Fikk ikke kontakt over nettet. Prøv igjen senere."
    else -> message ?: "Ukjent feil"
}

/**
 * Fetches transactions from SpareBank 1 with the user's own keys and uploads
 * them to Privatregnskap.
 *
 * The two sides are kept apart. The bank is reached through [Sb1Api] with keys
 * from [Sb1Store]; Privatregnskap is reached through [ApiService] and is only
 * ever handed transactions, never anything that opens the bank.
 */
@Singleton
class BankSyncRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val store: Sb1Store,
    private val sb1: Sb1Api,
    private val apiService: ApiService,
    private val tokenRepository: TokenRepository
) {
    val status: StateFlow<Sb1Status> = store.status

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    private val _browserLoginFailures = MutableSharedFlow<String>(extraBufferCapacity = 1)

    /** What went wrong when a login came back through the browser, worded for the user. */
    val browserLoginFailures: SharedFlow<String> = _browserLoginFailures.asSharedFlow()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val syncMutex = Mutex()
    private val tokenMutex = Mutex()
    private val loginMutex = Mutex()

    // Lasts ten minutes at the bank and is cheap to get again, so it is never stored
    @Volatile private var accessToken: String? = null
    @Volatile private var accessTokenExpiresAt = 0L

    @Volatile private var completedState: String? = null
    @Volatile private var listenerJob: Job? = null

    // ─── Setup ───────────────────────────────────────────────────────────────

    /** Reads the stored state, and checks whose it is when the server can be asked. */
    suspend fun load(): Sb1Status = withContext(Dispatchers.IO) {
        store.load()
        try {
            ensureOwner()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Offline or logged out: every action that uses the keys checks again
        }
        if (store.links().isNotEmpty()) schedule()
        store.status.value
    }

    /**
     * The keys are personal. If someone else has logged in to Privatregnskap
     * on this device since they were entered, they are removed, not used.
     */
    private suspend fun ensureOwner() {
        val me = apiService.getMe().id
        val owner = store.ownerUserId
        if (owner != null && owner != me) {
            wipeLocal()
            throw BankSyncException("Banknøklene på denne enheten tilhørte en annen bruker og er fjernet.")
        }
    }

    suspend fun saveClient(clientId: String, clientSecret: String) = withContext(Dispatchers.IO) {
        val me = apiService.getMe().id
        forgetAccessToken()
        store.saveClient(clientId.trim(), clientSecret.trim(), me)
    }

    /** Removes the keys from this device and tells the server to stop expecting uploads. */
    suspend fun removeKeys() = withContext(Dispatchers.IO) {
        syncMutex.withLock {
            for (link in store.links()) {
                try {
                    apiService.disconnectBankConnection(link.ledgerId, link.connectionId)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    // The keys go regardless. A connection left behind on the
                    // server reports itself as silent after two weeks.
                }
            }
            wipeLocal()
        }
    }

    private suspend fun wipeLocal() {
        listenerJob?.cancel()
        forgetAccessToken()
        store.clear()
        WorkManager.getInstance(context).cancelUniqueWork(BankSyncWorker.WORK_NAME)
    }

    // ─── Login ───────────────────────────────────────────────────────────────

    /** Starts a login and returns the address at the bank to open. */
    suspend fun beginLogin(): String = withContext(Dispatchers.IO) {
        val clientId = store.clientId?.takeIf { it.isNotBlank() }
            ?: throw BankSyncException("Legg inn nøklene fra banken først.")
        val bytes = ByteArray(24)
        SecureRandom().nextBytes(bytes)
        val state = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
        store.pendingState = state
        sb1.authorizeUrl(clientId, state)
    }

    /**
     * Finishes a login from the address the bank sent the user back to.
     *
     * The address can arrive three ways: caught in the app's own browser view,
     * received by the listener, or pasted in by hand. They may race, so the
     * code is exchanged once and a second arrival of the same login is a no-op.
     */
    suspend fun completeLogin(callbackUrl: String) = withContext(Dispatchers.IO) {
        loginMutex.withLock {
            val uri = Uri.parse(callbackUrl.trim())
            fun param(name: String): String? =
                runCatching { uri.getQueryParameter(name) }.getOrNull()?.takeIf { it.isNotBlank() }

            val state = param("state")
            if (state != null && state == completedState) return@withLock

            param("error")?.let { error ->
                val description = param("error_description")
                throw BankSyncException(
                    "Banken avbrøt innloggingen (" + listOfNotNull(error, description).joinToString(": ").take(200) + ")"
                )
            }
            val code = param("code")
            if (code == null || state == null) {
                throw BankSyncException(
                    "Adressen mangler koden fra banken. Kopier hele adressen, fra http til slutten."
                )
            }
            if (state != store.pendingState) {
                throw BankSyncException("Adressen hører til et annet innloggingsforsøk. Start innloggingen på nytt.")
            }
            val clientId = store.clientId
            val clientSecret = store.clientSecret
            if (clientId.isNullOrBlank() || clientSecret.isNullOrBlank()) {
                throw BankSyncException("Legg inn nøklene fra banken først.")
            }

            val tokens = sb1.exchangeCode(clientId, clientSecret, code, state)
            val refreshToken = tokens.refreshToken
                ?: throw BankSyncException("Banken ga ingen nøkkel til å fornye innloggingen med.")
            store.saveRefreshToken(refreshToken, isLogin = true)
            remember(tokens)
            completedState = state
        }
    }

    /**
     * Waits for the bank's redirect when the login runs in the ordinary browser.
     *
     * Best effort only. Android may freeze the app while the browser is in
     * front, and then nothing answers; the screen has a field to paste the
     * address into for that case.
     */
    fun listenForBrowserCallback() {
        listenerJob?.cancel()
        listenerJob = scope.launch {
            val url = withTimeoutOrNull(LISTEN_TIMEOUT_MS) { awaitCallback() } ?: return@launch
            try {
                completeLogin(url)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _browserLoginFailures.tryEmit(e.bankSyncMessage())
            }
        }
    }

    fun stopListening() {
        listenerJob?.cancel()
        listenerJob = null
    }

    private suspend fun awaitCallback(): String? = withContext(Dispatchers.IO) {
        val server = try {
            ServerSocket(Sb1Api.REDIRECT_PORT, 4, InetAddress.getByName("127.0.0.1"))
        } catch (e: IOException) {
            // The port is taken. The paste field still works.
            return@withContext null
        }
        server.use {
            it.soTimeout = 1000
            acceptCallback(it) { isActive }
        }
    }

    private fun acceptCallback(server: ServerSocket, active: () -> Boolean): String? {
        while (active()) {
            val socket = try {
                server.accept()
            } catch (e: SocketTimeoutException) {
                continue
            } catch (e: IOException) {
                return null
            }
            val target = socket.use { answer(it) }
            if (target != null) return "http://localhost:${Sb1Api.REDIRECT_PORT}$target"
        }
        return null
    }

    /** Answers one request, and returns its path and query if it was the bank's redirect. */
    private fun answer(socket: Socket): String? = try {
        socket.soTimeout = 3000
        val requestLine = socket.getInputStream().bufferedReader(Charsets.ISO_8859_1).readLine().orEmpty()
        val target = requestLine.split(' ').getOrNull(1).orEmpty()
        val isCallback = target.startsWith(Sb1Api.REDIRECT_PATH)

        val body = (if (isCallback) CALLBACK_PAGE else "Not found").toByteArray(Charsets.UTF_8)
        val head = "HTTP/1.1 ${if (isCallback) "200 OK" else "404 Not Found"}\r\n" +
            "Content-Type: text/html; charset=utf-8\r\n" +
            "Content-Length: ${body.size}\r\n" +
            "Connection: close\r\n\r\n"
        socket.getOutputStream().apply {
            write(head.toByteArray(Charsets.US_ASCII))
            write(body)
            flush()
        }
        target.takeIf { isCallback }
    } catch (e: IOException) {
        null
    }

    // ─── Access to the bank ──────────────────────────────────────────────────

    private fun remember(tokens: Sb1Tokens) {
        accessToken = tokens.accessToken
        // Renew a minute early rather than have a call fail on the last second
        accessTokenExpiresAt = System.currentTimeMillis() + (tokens.expiresInSeconds - 60) * 1000
    }

    private suspend fun forgetAccessToken() = tokenMutex.withLock {
        accessToken = null
        accessTokenExpiresAt = 0L
    }

    /**
     * One at a time. The bank replaces the refresh token on every use, so two
     * renewals side by side would leave one of them holding a dead token.
     */
    private suspend fun bankToken(): String = tokenMutex.withLock {
        val cached = accessToken
        if (cached != null && System.currentTimeMillis() < accessTokenExpiresAt) return@withLock cached

        val clientId = store.clientId
        val clientSecret = store.clientSecret
        val refreshToken = store.refreshToken
        if (clientId.isNullOrBlank() || clientSecret.isNullOrBlank() || refreshToken.isNullOrBlank()) {
            throw NeedsLoginException()
        }

        val tokens = try {
            sb1.refresh(clientId, clientSecret, refreshToken)
        } catch (e: Sb1HttpException) {
            if (e.error == "invalid_grant") {
                accessToken = null
                val gone = NeedsLoginException()
                store.forgetLogin(gone.message.orEmpty())
                throw gone
            }
            throw e
        }
        // The old token died when the bank answered. Write the new one down
        // before anything else can go wrong.
        tokens.refreshToken?.let { store.saveRefreshToken(it, isLogin = false) }
        remember(tokens)
        tokens.accessToken
    }

    private suspend fun <T> withBank(call: suspend (String) -> T): T =
        try {
            call(bankToken())
        } catch (e: Sb1HttpException) {
            if (e.status != 401) throw e
            // The token was turned down before its time. Get a new one and try once more.
            forgetAccessToken()
            call(bankToken())
        }

    /** The accounts the bank lets this login see. */
    suspend fun bankAccounts(): List<Sb1Account> = withContext(Dispatchers.IO) {
        ensureOwner()
        withBank { sb1.accounts(it) }
    }

    // ─── Links ───────────────────────────────────────────────────────────────

    /** The server's view of the connections in one ledger. */
    suspend fun serverConnections(ledgerId: Int): List<PushConnectionResponse> =
        apiService.getPushConnections(ledgerId)

    suspend fun link(
        ledgerId: Int,
        bankAccount: BankAccountResponse,
        account: Sb1Account,
        from: LocalDate
    ) = withContext(Dispatchers.IO) {
        ensureOwner()
        val connection = apiService.createPushConnection(
            ledgerId,
            PushConnectionCreateRequest(
                bankAccountId = bankAccount.id,
                externalAccountId = account.accountNumber,
                externalAccountName = account.name.take(255),
                externalBankId = BANK_ID,
                initialSyncFromDate = from.toString()
            )
        )
        // A connection that already existed keeps its own start date and may
        // have been filled before, from this device or another. Carry on from there.
        val link = Sb1Link(
            ledgerId = ledgerId,
            connectionId = connection.id,
            bankAccountId = bankAccount.id,
            bankAccountName = bankAccount.name,
            accountNumber = account.accountNumber,
            accountName = account.name,
            syncFrom = connection.initialSyncFromDate ?: from.toString(),
            syncedTo = connection.lastSuccessfulSyncAt?.take(10)
        )
        store.saveLinks(store.links().filterNot { it.connectionId == connection.id } + link)
        schedule()
    }

    suspend fun unlink(link: Sb1Link) = withContext(Dispatchers.IO) {
        syncMutex.withLock {
            try {
                apiService.disconnectBankConnection(link.ledgerId, link.connectionId)
            } catch (e: HttpException) {
                // Already gone, or no longer ours to touch: nothing waits for
                // uploads there. Anything else must succeed first, or the
                // server would sit expecting a device that has stopped.
                if (e.code() !in listOf(400, 403, 404)) throw e
            }
            val remaining = store.links().filterNot { it.connectionId == link.connectionId }
            store.saveLinks(remaining)
            if (remaining.isEmpty()) {
                WorkManager.getInstance(context).cancelUniqueWork(BankSyncWorker.WORK_NAME)
            }
        }
    }

    /** Twice a day in the background. Keeps the bank login alive as a side effect. */
    private fun schedule() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = PeriodicWorkRequestBuilder<BankSyncWorker>(SYNC_INTERVAL_HOURS, TimeUnit.HOURS)
            .setInitialDelay(SYNC_INTERVAL_HOURS, TimeUnit.HOURS)
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            BankSyncWorker.WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            request
        )
    }

    // ─── Sync ────────────────────────────────────────────────────────────────

    suspend fun syncAll(): SyncOutcome = withContext(Dispatchers.IO) {
        if (!tokenRepository.isLoggedIn()) return@withContext SyncOutcome.Idle
        syncMutex.withLock {
            _isSyncing.value = true
            try {
                runSync()
            } finally {
                _isSyncing.value = false
            }
        }
    }

    private suspend fun runSync(): SyncOutcome {
        if (store.links().isEmpty() || store.refreshToken.isNullOrBlank()) return SyncOutcome.Idle

        return try {
            ensureOwner()
            val accounts = withBank { sb1.accounts(it) }.associateBy { it.accountNumber }
            val connections = mutableMapOf<Int, List<PushConnectionResponse>>()
            val problems = mutableListOf<String>()
            var imported = 0

            for (link in store.links()) {
                try {
                    imported += syncLink(link, accounts, connections)
                } catch (e: BankSyncException) {
                    // This account's own trouble. The others can still go through.
                    problems += "${link.accountName}: ${e.message}"
                } catch (e: HttpException) {
                    problems += "${link.accountName}: ${e.bankSyncMessage()}"
                } catch (e: Sb1HttpException) {
                    // A bank that is down or busy is the same for every account
                    if (e.status == 401 || e.status == 429 || e.status >= 500) throw e
                    problems += "${link.accountName}: ${e.message}"
                }
            }

            val message = when (imported) {
                0 -> "Ingen nye transaksjoner"
                1 -> "1 ny transaksjon i posteringskøen"
                else -> "$imported nye transaksjoner i posteringskøen"
            }
            store.saveSyncResult(message, problems.takeIf { it.isNotEmpty() }?.joinToString("\n"))
            if (problems.isEmpty()) SyncOutcome.Done(imported, message)
            else SyncOutcome.Failed(problems.joinToString("\n"), retryable = false)
        } catch (e: CancellationException) {
            throw e
        } catch (e: NeedsLoginException) {
            SyncOutcome.NeedsLogin
        } catch (e: Sb1HttpException) {
            val message = e.message ?: "Banken svarte med en feil"
            store.saveSyncError(message)
            SyncOutcome.Failed(message, retryable = e.status == 429 || e.status >= 500)
        } catch (e: Exception) {
            val message = e.bankSyncMessage()
            store.saveSyncError(message)
            SyncOutcome.Failed(message, retryable = e is IOException)
        }
    }

    /** Fetches and uploads for one account. Returns how many transactions were new. */
    private suspend fun syncLink(
        link: Sb1Link,
        accounts: Map<String, Sb1Account>,
        connections: MutableMap<Int, List<PushConnectionResponse>>
    ): Int {
        val account = accounts[link.accountNumber]
            ?: throw BankSyncException("Banken viser ikke lenger denne kontoen.")
        val ledgerConnections = connections.getOrPut(link.ledgerId) {
            apiService.getPushConnections(link.ledgerId)
        }
        val connection = ledgerConnections.firstOrNull { it.id == link.connectionId }
            ?: throw BankSyncException("Koblingen finnes ikke lenger i regnskapet. Koble kontoen til på nytt.")

        val today = LocalDate.now(OSLO)
        // Go back over the last two weeks every time: a purchase is booked
        // days after it is made, and with the date of the purchase
        val wanted = link.syncedTo.toDateOrNull()?.minusDays(OVERLAP_DAYS)
            ?: link.syncFrom.toDateOrNull()
            ?: connection.initialSyncFromDate.toDateOrNull()
            ?: today.minusDays(DEFAULT_HISTORY_DAYS)
        val earliest = today.minusYears(MAX_HISTORY_YEARS).plusDays(1)
        val start = when {
            wanted.isBefore(earliest) -> earliest
            wanted.isAfter(today) -> today
            else -> wanted
        }

        // Neighbouring windows share a day, so nothing is lost whichever way
        // the bank reads the end date. What comes twice is sorted out below.
        val rows = mutableListOf<JSONObject>()
        var windowStart = start
        while (true) {
            val candidate = windowStart.plusDays(WINDOW_DAYS)
            val windowEnd = if (candidate.isAfter(today)) today else candidate
            rows += fetchWindow(account.key, windowStart, windowEnd)
            if (!windowEnd.isBefore(today)) break
            windowStart = windowEnd
        }

        val mapped = LinkedHashMap<String, JSONObject>()
        for (row in rows) {
            val transaction = mapSb1Transaction(row) ?: continue
            mapped[transaction.getString("external_id")] = transaction
        }
        val chunks = mapped.values
            .sortedBy { it.getString("transaction_date") }
            .chunked(UPLOAD_CHUNK)
            // Nothing new is sent too: it tells the server this device is still looking
            .ifEmpty { listOf(emptyList<JSONObject>()) }

        var imported = 0
        for (chunk in chunks) {
            val body = JSONObject().put("transactions", JSONArray(chunk)).toString().toRequestBody(JSON)
            val response = apiService.uploadBankTransactions(link.ledgerId, link.connectionId, body)
            if (response.status == "failed") {
                throw BankSyncException(response.message ?: "Privatregnskap tok ikke imot transaksjonene.")
            }
            imported += response.imported
        }

        // Only now is the period covered. Had it been marked earlier, a fetch
        // that stopped half way would leave a hole nothing came back for.
        store.saveLinks(
            store.links().map {
                if (it.connectionId == link.connectionId) it.copy(syncedTo = today.toString()) else it
            }
        )
        return imported
    }

    private suspend fun fetchWindow(accountKey: String, from: LocalDate, to: LocalDate): List<JSONObject> {
        val rows = withBank { sb1.transactions(it, accountKey, from, to) }
        // The bank allows about sixty calls a minute
        delay(CALL_PAUSE_MS)
        val days = ChronoUnit.DAYS.between(from, to)
        if (rows.size < SPLIT_ABOVE_ROWS || days < 2) return rows

        // How many rows one answer can hold is not documented. This many is
        // more than has been seen to come through, so ask again in halves.
        val middle = from.plusDays(days / 2)
        return fetchWindow(accountKey, from, middle) + fetchWindow(accountKey, middle, to)
    }

    private fun String?.toDateOrNull(): LocalDate? =
        this?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }

    companion object {
        private const val BANK_ID = "sparebank1"
        private val OSLO: ZoneId = ZoneId.of("Europe/Oslo")
        private val JSON = "application/json".toMediaType()

        private const val SYNC_INTERVAL_HOURS = 12L
        private const val OVERLAP_DAYS = 14L
        private const val DEFAULT_HISTORY_DAYS = 30L
        private const val MAX_HISTORY_YEARS = 5L
        private const val WINDOW_DAYS = 60L
        private const val SPLIT_ABOVE_ROWS = 400
        private const val UPLOAD_CHUNK = 200
        private const val CALL_PAUSE_MS = 1100L
        private const val LISTEN_TIMEOUT_MS = 10 * 60 * 1000L

        private const val CALLBACK_PAGE =
            "<!doctype html><html lang=\"no\"><head><meta charset=\"utf-8\">" +
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
                "<title>Privatregnskap</title></head>" +
                "<body style=\"font-family:sans-serif;padding:2em\">" +
                "<h2>Ferdig</h2><p>Gå tilbake til Privatregnskap.</p></body></html>"
    }
}
