package eu.privatregnskap.app.ui.common

import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

fun showBiometricPrompt(
    activity: FragmentActivity,
    title: String,
    cipher: javax.crypto.Cipher,
    onSuccess: (BiometricPrompt.AuthenticationResult) -> Unit,
    onError: (String) -> Unit = {}
) {
    val executor = ContextCompat.getMainExecutor(activity)
    val prompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
            onSuccess(result)
        }
        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
            if (errorCode != BiometricPrompt.ERROR_USER_CANCELED &&
                errorCode != BiometricPrompt.ERROR_NEGATIVE_BUTTON) {
                onError(errString.toString())
            }
        }
    })
    val promptInfo = BiometricPrompt.PromptInfo.Builder()
        .setTitle(title)
        .setNegativeButtonText("Avbryt")
        .build()
    prompt.authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
}
