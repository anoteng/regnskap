package eu.privatregnskap.app.ui.profile

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import eu.privatregnskap.app.data.network.dto.PasskeyCredentialResponse
import eu.privatregnskap.app.data.preferences.NotificationPreferences
import eu.privatregnskap.app.data.repository.PasskeyRepository
import eu.privatregnskap.app.worker.PostingQueueCheckWorker
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit
import javax.inject.Inject

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val passkeyRepository: PasskeyRepository,
    private val notificationPreferences: NotificationPreferences,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _credentials = MutableStateFlow<List<PasskeyCredentialResponse>>(emptyList())
    val credentials: StateFlow<List<PasskeyCredentialResponse>> = _credentials.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private var pendingRegisterOptionsJson: String? = null

    private val _registerOptionsState = MutableStateFlow<RegisterOptionsState>(RegisterOptionsState.Idle)
    val registerOptionsState: StateFlow<RegisterOptionsState> = _registerOptionsState.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

    val queueNotificationsEnabled: StateFlow<Boolean> =
        notificationPreferences.queueNotificationsEnabled
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    init {
        loadCredentials()
    }

    fun loadCredentials() {
        viewModelScope.launch {
            _isLoading.value = true
            passkeyRepository.listCredentials()
                .onSuccess { _credentials.value = it }
                .onFailure { _message.emit("Kunne ikke hente passkeys: ${it.message}") }
            _isLoading.value = false
        }
    }

    fun deleteCredential(id: Int) {
        viewModelScope.launch {
            passkeyRepository.deleteCredential(id)
                .onSuccess {
                    _credentials.value = _credentials.value.filter { it.id != id }
                    _message.emit("Passkey slettet")
                }
                .onFailure { _message.emit("Kunne ikke slette passkey: ${it.message}") }
        }
    }

    fun renameCredential(id: Int, newName: String) {
        viewModelScope.launch {
            passkeyRepository.renameCredential(id, newName)
                .onSuccess { updated ->
                    _credentials.value = _credentials.value.map { if (it.id == id) updated else it }
                }
                .onFailure { _message.emit("Kunne ikke endre navn: ${it.message}") }
        }
    }

    fun beginRegistration(credentialName: String?) {
        viewModelScope.launch {
            _registerOptionsState.value = RegisterOptionsState.Loading
            passkeyRepository.registerBegin(credentialName)
                .onSuccess { json ->
                    pendingRegisterOptionsJson = json
                    _registerOptionsState.value = RegisterOptionsState.Ready(json)
                }
                .onFailure {
                    _registerOptionsState.value = RegisterOptionsState.Idle
                    _message.emit("Kunne ikke starte passkey-registrering: ${it.message}")
                }
        }
    }

    fun completeRegistration(registrationJson: String) {
        val optionsJson = pendingRegisterOptionsJson ?: "{}"
        pendingRegisterOptionsJson = null
        _registerOptionsState.value = RegisterOptionsState.Idle
        viewModelScope.launch {
            passkeyRepository.registerComplete(registrationJson, optionsJson)
                .onSuccess {
                    _message.emit("Passkey lagt til")
                    loadCredentials()
                }
                .onFailure { _message.emit("Registrering feilet: ${it.message}") }
        }
    }

    fun resetRegisterOptionsState() {
        pendingRegisterOptionsJson = null
        _registerOptionsState.value = RegisterOptionsState.Idle
    }

    fun setQueueNotificationsEnabled(enabled: Boolean) {
        viewModelScope.launch {
            notificationPreferences.setQueueNotificationsEnabled(enabled)
            val workManager = WorkManager.getInstance(context)
            if (enabled) {
                val request = PeriodicWorkRequestBuilder<PostingQueueCheckWorker>(15, TimeUnit.MINUTES)
                    .build()
                workManager.enqueueUniquePeriodicWork(
                    PostingQueueCheckWorker.WORK_NAME,
                    ExistingPeriodicWorkPolicy.KEEP,
                    request
                )
            } else {
                workManager.cancelUniqueWork(PostingQueueCheckWorker.WORK_NAME)
            }
        }
    }
}

sealed class RegisterOptionsState {
    object Idle : RegisterOptionsState()
    object Loading : RegisterOptionsState()
    data class Ready(val optionsJson: String) : RegisterOptionsState()
}
