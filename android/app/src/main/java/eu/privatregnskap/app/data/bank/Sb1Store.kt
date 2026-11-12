package eu.privatregnskap.app.data.bank

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

/**
 * One bank account this device fetches for, and the connection it uploads to.
 *
 * [syncedTo] is this device's own record of how far it has come. The server
 * marks a connection as synced on the first upload it receives, and a long
 * first fetch that stops half way must start over from [syncFrom] and not from
 * the day it stopped.
 */
data class Sb1Link(
    val ledgerId: Int,
    val connectionId: Int,
    val bankAccountId: Int,
    val bankAccountName: String,
    val accountNumber: String,
    val accountName: String,
    val syncFrom: String? = null,
    val syncedTo: String? = null
)

/** What the screens may know. The keys themselves never leave the store. */
data class Sb1Status(
    val hasClient: Boolean = false,
    val loggedIn: Boolean = false,
    val loginAt: Long? = null,
    val links: List<Sb1Link> = emptyList(),
    val lastSyncAt: Long? = null,
    val lastSyncMessage: String? = null,
    val lastError: String? = null
)

/**
 * Everything the SpareBank 1 sync keeps, encrypted with a key held by the
 * Android Keystore.
 *
 * The bank's terms give the key to the customer personally and forbid passing
 * it on, so the client id, the client secret and the refresh token live here
 * and nowhere else: they are not sent to Privatregnskap, and the file is kept
 * out of device backups.
 */
@Singleton
class Sb1Store @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val prefs: SharedPreferences by lazy {
        try {
            open()
        } catch (e: Exception) {
            // A keystore that no longer opens the file cannot be argued with.
            // Start empty; the user enters the keys again.
            context.deleteSharedPreferences(FILE_NAME)
            open()
        }
    }

    private fun open(): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    private val _status = MutableStateFlow(Sb1Status())
    val status: StateFlow<Sb1Status> = _status.asStateFlow()

    /** Reads the stored state into [status]. Touches the keystore: call off the main thread. */
    fun load(): Sb1Status = publish()

    private fun publish(): Sb1Status {
        val status = Sb1Status(
            hasClient = !clientId.isNullOrBlank() && !clientSecret.isNullOrBlank(),
            loggedIn = !refreshToken.isNullOrBlank(),
            loginAt = prefs.getLong(KEY_LOGIN_AT, 0L).takeIf { it > 0 },
            links = links(),
            lastSyncAt = prefs.getLong(KEY_LAST_SYNC_AT, 0L).takeIf { it > 0 },
            lastSyncMessage = prefs.getString(KEY_LAST_SYNC_MESSAGE, null),
            lastError = prefs.getString(KEY_LAST_ERROR, null)
        )
        _status.value = status
        return status
    }

    val clientId: String? get() = prefs.getString(KEY_CLIENT_ID, null)
    val clientSecret: String? get() = prefs.getString(KEY_CLIENT_SECRET, null)
    val refreshToken: String? get() = prefs.getString(KEY_REFRESH_TOKEN, null)

    /** The Privatregnskap user the keys were entered by. */
    val ownerUserId: Int? get() = prefs.getInt(KEY_OWNER_USER_ID, -1).takeIf { it >= 0 }

    fun saveClient(clientId: String, clientSecret: String, ownerUserId: Int) {
        // New keys mean a new client at the bank: the old login does not belong to it
        prefs.edit()
            .putString(KEY_CLIENT_ID, clientId)
            .putString(KEY_CLIENT_SECRET, clientSecret)
            .putInt(KEY_OWNER_USER_ID, ownerUserId)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_LOGIN_AT)
            .remove(KEY_PENDING_STATE)
            .commit()
        publish()
    }

    /**
     * Stores a refresh token before anything else happens.
     *
     * The bank replaces the token every time it is used and the old one dies
     * at once. A token that is received but not written is a new BankID login,
     * so this waits for the disk.
     */
    fun saveRefreshToken(refreshToken: String, isLogin: Boolean) {
        val editor = prefs.edit().putString(KEY_REFRESH_TOKEN, refreshToken)
        if (isLogin) {
            editor.putLong(KEY_LOGIN_AT, System.currentTimeMillis())
                .remove(KEY_PENDING_STATE)
                .remove(KEY_LAST_ERROR)
        }
        editor.commit()
        publish()
    }

    /** The bank no longer accepts the token: only a new BankID login helps. */
    fun forgetLogin(reason: String) {
        prefs.edit()
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_LOGIN_AT)
            .putString(KEY_LAST_ERROR, reason)
            .commit()
        publish()
    }

    var pendingState: String?
        get() = prefs.getString(KEY_PENDING_STATE, null)
        set(value) {
            val editor = prefs.edit()
            if (value == null) editor.remove(KEY_PENDING_STATE) else editor.putString(KEY_PENDING_STATE, value)
            editor.commit()
        }

    fun links(): List<Sb1Link> {
        val raw = prefs.getString(KEY_LINKS, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            (0 until array.length()).map { i ->
                val o = array.getJSONObject(i)
                Sb1Link(
                    ledgerId = o.getInt("ledgerId"),
                    connectionId = o.getInt("connectionId"),
                    bankAccountId = o.getInt("bankAccountId"),
                    bankAccountName = o.optString("bankAccountName"),
                    accountNumber = o.getString("accountNumber"),
                    accountName = o.optString("accountName"),
                    syncFrom = o.optString("syncFrom").takeIf { it.isNotBlank() },
                    syncedTo = o.optString("syncedTo").takeIf { it.isNotBlank() }
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun saveLinks(links: List<Sb1Link>) {
        val array = JSONArray()
        links.forEach { link ->
            array.put(
                JSONObject()
                    .put("ledgerId", link.ledgerId)
                    .put("connectionId", link.connectionId)
                    .put("bankAccountId", link.bankAccountId)
                    .put("bankAccountName", link.bankAccountName)
                    .put("accountNumber", link.accountNumber)
                    .put("accountName", link.accountName)
                    .put("syncFrom", link.syncFrom ?: "")
                    .put("syncedTo", link.syncedTo ?: "")
            )
        }
        prefs.edit().putString(KEY_LINKS, array.toString()).commit()
        publish()
    }

    /** A sync that ran to the end. [error] names the accounts it did not get through for, if any. */
    fun saveSyncResult(message: String, error: String?) {
        val editor = prefs.edit()
            .putLong(KEY_LAST_SYNC_AT, System.currentTimeMillis())
            .putString(KEY_LAST_SYNC_MESSAGE, message)
        if (error == null) editor.remove(KEY_LAST_ERROR) else editor.putString(KEY_LAST_ERROR, error)
        editor.commit()
        publish()
    }

    /** A sync that did not get through. The time of the last one that did is left alone. */
    fun saveSyncError(error: String) {
        prefs.edit().putString(KEY_LAST_ERROR, error).commit()
        publish()
    }

    /** Removes the keys, the login and the links from this device. */
    fun clear() {
        prefs.edit().clear().commit()
        publish()
    }

    companion object {
        const val FILE_NAME = "sb1_sync_secure_prefs"
        private const val KEY_CLIENT_ID = "client_id"
        private const val KEY_CLIENT_SECRET = "client_secret"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_OWNER_USER_ID = "owner_user_id"
        private const val KEY_LOGIN_AT = "login_at"
        private const val KEY_PENDING_STATE = "pending_state"
        private const val KEY_LINKS = "links"
        private const val KEY_LAST_SYNC_AT = "last_sync_at"
        private const val KEY_LAST_SYNC_MESSAGE = "last_sync_message"
        private const val KEY_LAST_ERROR = "last_error"
    }
}
