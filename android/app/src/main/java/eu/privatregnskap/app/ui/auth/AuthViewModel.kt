package eu.privatregnskap.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.AppLockManager
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
    private val tokenRepository: TokenRepository,
    private val appLockManager: AppLockManager
) : ViewModel() {

    val isLoggedIn = authRepository.isLoggedIn

    // Only used for Loading/Error display — never emits Success
    private val _loginState = MutableStateFlow<UiState<Unit>>(UiState.Idle)
    val loginState: StateFlow<UiState<Unit>> = _loginState.asStateFlow()

    private val _passkeyOptionsState = MutableStateFlow<UiState<String>>(UiState.Idle)
    val passkeyOptionsState: StateFlow<UiState<String>> = _passkeyOptionsState.asStateFlow()

    private var pendingPasskeyOptionsJson: String? = null

    private val _forgotPasswordState = MutableStateFlow<UiState<Unit>>(UiState.Idle)
    val forgotPasswordState: StateFlow<UiState<Unit>> = _forgotPasswordState.asStateFlow()

    // Navigation trigger — set to true when app should navigate to home
    private val _navigateToHome = MutableStateFlow(false)
    val navigateToHome: StateFlow<Boolean> = _navigateToHome.asStateFlow()

    // Biometric offer shown after first successful login on eligible devices
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
            when {
                result.isSuccess -> {
                    _loginState.value = UiState.Idle
                    handlePostLogin()
                }
                else -> _loginState.value =
                    UiState.Error(result.exceptionOrNull()?.message ?: "Innlogging feilet")
            }
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
            when {
                result.isSuccess -> {
                    _loginState.value = UiState.Idle
                    handlePostLogin()
                }
                else -> _loginState.value =
                    UiState.Error(result.exceptionOrNull()?.message ?: "Passkey-innlogging feilet")
            }
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
            when {
                result.isSuccess -> {
                    appLockManager.unlock()
                    _loginState.value = UiState.Idle
                    _navigateToHome.value = true
                }
                else -> {
                    // Token is invalid (likely revoked) — clear biometric data so user can re-enable
                    biometricRepository.clearBiometricData()
                    _loginState.value = UiState.Error(
                        "Biometri-token er ikke lenger gyldig. Logg inn med passord for å reaktivere."
                    )
                }
            }
        }
    }

    fun enableBiometricWithCipher(cipher: Cipher) {
        viewModelScope.launch {
            // Create a dedicated token separate from the session token,
            // so regular logout doesn't invalidate biometric login.
            val dedicatedToken = authRepository.createBiometricToken().getOrElse {
                // Fallback to session token if request fails
                tokenRepository.getRefreshToken() ?: return@launch
            }
            biometricRepository.encryptAndStore(dedicatedToken, cipher)
            _showBiometricOffer.value = false
            _navigateToHome.value = true
        }
    }

    fun dismissBiometricOffer() {
        biometricRepository.setDeclinedOffer()
        _showBiometricOffer.value = false
        _navigateToHome.value = true
    }

    fun disableBiometricLogin() {
        // Clear local biometric data — dedicated token expires server-side after 30 days
        biometricRepository.clearBiometricData()
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

    fun resetNavigation() { _navigateToHome.value = false }
    fun resetPasskeyOptionsState() { _passkeyOptionsState.value = UiState.Idle }
    fun resetForgotPasswordState() { _forgotPasswordState.value = UiState.Idle }

    private fun handlePostLogin() {
        // Unlock immediately so the lock navigation in NavGraph doesn't interrupt
        // the biometric offer dialog or any other post-login UI
        appLockManager.unlock()
        val shouldOffer = biometricRepository.isBiometricAvailable()
            && !biometricRepository.isBiometricLoginEnabled()
            && !biometricRepository.hasDeclinedOffer()
        if (shouldOffer) {
            _showBiometricOffer.value = true
        } else {
            _navigateToHome.value = true
        }
    }
}
