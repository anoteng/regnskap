package eu.privatregnskap.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.repository.AuthRepository
import eu.privatregnskap.app.data.repository.BiometricRepository
import eu.privatregnskap.app.data.repository.TokenRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.crypto.Cipher
import javax.inject.Inject

sealed class UiState<out T> {
    object Idle : UiState<Nothing>()
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String) : UiState<Nothing>()
}

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val biometricRepository: BiometricRepository,
    private val tokenRepository: TokenRepository
) : ViewModel() {

    val isLoggedIn = authRepository.isLoggedIn

    private val _loginState = MutableStateFlow<UiState<Unit>>(UiState.Idle)
    val loginState: StateFlow<UiState<Unit>> = _loginState.asStateFlow()

    private val _passkeyOptionsState = MutableStateFlow<UiState<String>>(UiState.Idle)
    val passkeyOptionsState: StateFlow<UiState<String>> = _passkeyOptionsState.asStateFlow()

    private var pendingPasskeyOptionsJson: String? = null

    private val _forgotPasswordState = MutableStateFlow<UiState<Unit>>(UiState.Idle)
    val forgotPasswordState: StateFlow<UiState<Unit>> = _forgotPasswordState.asStateFlow()

    private val _showBiometricOffer = MutableStateFlow(false)
    val showBiometricOffer: StateFlow<Boolean> = _showBiometricOffer.asStateFlow()

    fun isBiometricAvailable() = biometricRepository.isBiometricAvailable()
    fun isBiometricLoginEnabled() = biometricRepository.isBiometricLoginEnabled()

    fun getCipherForEncryption(): Cipher = biometricRepository.getCipherForEncryption()
    fun getCipherForDecryption(): Cipher? = biometricRepository.getCipherForDecryption()

    fun login(email: String, password: String) {
        viewModelScope.launch {
            _loginState.value = UiState.Loading
            val result = authRepository.login(email.trim(), password)
            if (result.isSuccess) {
                checkBiometricOffer()
            }
            _loginState.value = result.fold(
                onSuccess = { UiState.Success(Unit) },
                onFailure = { UiState.Error(it.message ?: "Innlogging feilet") }
            )
        }
    }

    fun getPasskeyOptions() {
        viewModelScope.launch {
            _passkeyOptionsState.value = UiState.Loading
            val result = authRepository.loginWithPasskey("{}")
            result.onSuccess { pendingPasskeyOptionsJson = it }
            _passkeyOptionsState.value = result.fold(
                onSuccess = { UiState.Success(it) },
                onFailure = { UiState.Error(it.message ?: "Kunne ikke hente passkey-alternativer") }
            )
        }
    }

    fun verifyPasskeyLogin(credentialJson: String) {
        val optionsJson = pendingPasskeyOptionsJson ?: "{}"
        pendingPasskeyOptionsJson = null
        viewModelScope.launch {
            _loginState.value = UiState.Loading
            val result = authRepository.verifyPasskeyLogin(credentialJson, optionsJson)
            if (result.isSuccess) {
                checkBiometricOffer()
            }
            _loginState.value = result.fold(
                onSuccess = { UiState.Success(Unit) },
                onFailure = { UiState.Error(it.message ?: "Passkey-innlogging feilet") }
            )
        }
    }

    fun loginWithBiometricCipher(cipher: Cipher) {
        val token = biometricRepository.decryptToken(cipher) ?: run {
            _loginState.value = UiState.Error("Kunne ikke dekryptere biometri-data")
            return
        }
        viewModelScope.launch {
            _loginState.value = UiState.Loading
            val result = authRepository.refreshLogin(token)
            _loginState.value = result.fold(
                onSuccess = { UiState.Success(Unit) },
                onFailure = { UiState.Error(it.message ?: "Biometri-innlogging feilet") }
            )
        }
    }

    fun enableBiometricWithCipher(cipher: Cipher) {
        val refreshToken = tokenRepository.getRefreshToken() ?: return
        biometricRepository.encryptAndStore(refreshToken, cipher)
        _showBiometricOffer.value = false
    }

    fun dismissBiometricOffer() {
        _showBiometricOffer.value = false
    }

    fun requestPasswordReset(email: String) {
        viewModelScope.launch {
            _forgotPasswordState.value = UiState.Loading
            val result = authRepository.requestPasswordReset(email.trim())
            _forgotPasswordState.value = result.fold(
                onSuccess = { UiState.Success(Unit) },
                onFailure = { UiState.Error(it.message ?: "Forespørsel feilet") }
            )
        }
    }

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }

    fun resetLoginState() { _loginState.value = UiState.Idle }
    fun resetPasskeyOptionsState() { _passkeyOptionsState.value = UiState.Idle }
    fun resetForgotPasswordState() { _forgotPasswordState.value = UiState.Idle }

    private fun checkBiometricOffer() {
        if (biometricRepository.isBiometricAvailable() && !biometricRepository.isBiometricLoginEnabled()) {
            _showBiometricOffer.value = true
        }
    }
}
