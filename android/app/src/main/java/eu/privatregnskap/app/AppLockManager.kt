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

    // Compute initial state at construction so cold-start lock is immediate
    private val _isLocked = MutableStateFlow(computeIsLocked())
    val isLocked: StateFlow<Boolean> = _isLocked.asStateFlow()

    private fun computeIsLocked(): Boolean {
        val last = prefs.getLong(KEY, 0L)
        return last > 0L && System.currentTimeMillis() - last > TIMEOUT_MS
    }

    fun onAppBackground() {
        prefs.edit().putLong(KEY, System.currentTimeMillis()).apply()
    }

    fun onAppForeground() {
        if (computeIsLocked()) _isLocked.value = true
    }

    fun unlock() {
        _isLocked.value = false
        prefs.edit().remove(KEY).apply()
    }
}
