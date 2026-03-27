package eu.privatregnskap.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NotificationPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    companion object {
        val QUEUE_NOTIFICATIONS_ENABLED = booleanPreferencesKey("queue_notifications_enabled")
        val QUEUE_LAST_COUNT = intPreferencesKey("queue_last_count")
    }

    val queueNotificationsEnabled: Flow<Boolean> =
        dataStore.data.map { it[QUEUE_NOTIFICATIONS_ENABLED] ?: false }

    suspend fun setQueueNotificationsEnabled(enabled: Boolean) {
        dataStore.edit { it[QUEUE_NOTIFICATIONS_ENABLED] = enabled }
    }

    suspend fun getLastQueueCount(): Int =
        dataStore.data.first()[QUEUE_LAST_COUNT] ?: 0

    suspend fun setLastQueueCount(count: Int) {
        dataStore.edit { it[QUEUE_LAST_COUNT] = count }
    }
}
