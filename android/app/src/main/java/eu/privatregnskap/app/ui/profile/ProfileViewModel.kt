package eu.privatregnskap.app.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.PasskeyCredentialResponse
import eu.privatregnskap.app.data.repository.PasskeyRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val passkeyRepository: PasskeyRepository
) : ViewModel() {

    private val _credentials = MutableStateFlow<List<PasskeyCredentialResponse>>(emptyList())
    val credentials: StateFlow<List<PasskeyCredentialResponse>> = _credentials.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    // Options JSON returned from begin registration, needed to complete it
    private var pendingRegisterOptionsJson: String? = null

    private val _registerOptionsState = MutableStateFlow<RegisterOptionsState>(RegisterOptionsState.Idle)
    val registerOptionsState: StateFlow<RegisterOptionsState> = _registerOptionsState.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

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
}

sealed class RegisterOptionsState {
    object Idle : RegisterOptionsState()
    object Loading : RegisterOptionsState()
    data class Ready(val optionsJson: String) : RegisterOptionsState()
}
