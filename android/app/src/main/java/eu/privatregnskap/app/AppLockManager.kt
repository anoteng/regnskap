package eu.privatregnskap.app

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AppLockManager @Inject constructor(
    @ApplicationContext context: Context
) {
    private val prefs = context.getSharedPreferences("app_lock_prefs", Context.MODE_PRIVATE)
    private val TIMEOUT_MS = 5 * 60 * 1000L
    private val KEY = "last_backgrounded_at"

    // In-memory: false on cold start or after explicit close, true once app has been running
    private var appWasRunning = false

    private val _isLocked = MutableStateFlow(false)
    val isLocked: StateFlow<Boolean> = _isLocked.asStateFlow()

    fun onAppForeground() {
        if (!appWasRunning || isTimedOut()) _isLocked.value = true
        appWasRunning = true
    }

    fun onAppBackground() {
        prefs.edit().putLong(KEY, System.currentTimeMillis()).apply()
    }

    fun onAppClosed() {
        // onStop (and thus onAppBackground) already ran before this, so timestamp is saved
        appWasRunning = false
    }

    private fun isTimedOut(): Boolean {
        val last = prefs.getLong(KEY, 0L)
        return last > 0L && System.currentTimeMillis() - last > TIMEOUT_MS
    }

    fun unlock() {
        _isLocked.value = false
        prefs.edit().remove(KEY).apply()
    }
}
