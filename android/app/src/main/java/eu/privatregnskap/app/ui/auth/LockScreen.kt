package eu.privatregnskap.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.ui.common.showBiometricPrompt

@Composable
fun LockScreen(
    onUnlocked: () -> Unit,
    viewModel: AuthViewModel = hiltViewModel()
) {
    val activity = LocalContext.current as FragmentActivity
    val navigateToHome by viewModel.navigateToHome.collectAsStateWithLifecycle()
    val loginState by viewModel.loginState.collectAsStateWithLifecycle()
    val biometricEnabled = remember { viewModel.isBiometricLoginEnabled() }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(navigateToHome) {
        if (navigateToHome) {
            viewModel.resetNavigation()
            onUnlocked()
        }
    }

    // Auto-prompt biometric on enter
    LaunchedEffect(Unit) {
        if (biometricEnabled) {
            val cipher = viewModel.getCipherForDecryption()
            if (cipher != null) {
                showBiometricPrompt(
                    activity = activity,
                    title = "Lås opp appen",
                    cipher = cipher,
                    onSuccess = { result ->
                        result.cryptoObject?.cipher?.let { viewModel.loginWithBiometricCipher(it) }
                    },
                    onError = { error = it }
                )
            } else {
                // Key invalidated — disable biometric so user falls back to manual login
                viewModel.disableBiometricLogin()
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Privatregnskap",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Appen er låst",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        val errorMessage = (loginState as? UiState.Error)?.message ?: error
        if (errorMessage != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        if (biometricEnabled) {
            Button(
                onClick = {
                    error = null
                    val cipher = viewModel.getCipherForDecryption()
                    if (cipher != null) {
                        showBiometricPrompt(
                            activity = activity,
                            title = "Lås opp appen",
                            cipher = cipher,
                            onSuccess = { result ->
                                result.cryptoObject?.cipher?.let { viewModel.loginWithBiometricCipher(it) }
                            },
                            onError = { error = it }
                        )
                    } else {
                        viewModel.disableBiometricLogin()
                        error = "Biometri-data er ikke lenger gyldig. Logg inn på nytt."
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = loginState !is UiState.Loading
            ) {
                if (loginState is UiState.Loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Lås opp med biometri")
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
        }

        OutlinedButton(
            onClick = { viewModel.logout() },
            modifier = Modifier.fillMaxWidth(),
            enabled = loginState !is UiState.Loading
        ) {
            Text("Logg inn på nytt")
        }
    }
}
