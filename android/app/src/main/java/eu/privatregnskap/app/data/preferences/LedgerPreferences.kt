package eu.privatregnskap.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LedgerPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    companion object {
        val SELECTED_LEDGER_ID = intPreferencesKey("selected_ledger_id")
    }

    val selectedLedgerId: Flow<Int?> =
        dataStore.data.map { it[SELECTED_LEDGER_ID] }

    suspend fun setSelectedLedgerId(ledgerId: Int) {
        dataStore.edit { it[SELECTED_LEDGER_ID] = ledgerId }
    }

    suspend fun clear() {
        dataStore.edit { it.remove(SELECTED_LEDGER_ID) }
    }
}
