package eu.privatregnskap.app.ui.auth

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.AppLockManager
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject

@HiltViewModel
class AppLockViewModel @Inject constructor(
    private val appLockManager: AppLockManager
) : ViewModel() {
    val isLocked: StateFlow<Boolean> = appLockManager.isLocked
    fun unlock() = appLockManager.unlock()
}
