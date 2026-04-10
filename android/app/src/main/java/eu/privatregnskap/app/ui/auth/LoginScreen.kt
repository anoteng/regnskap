package eu.privatregnskap.app.ui.auth

import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.autofill.ContentType
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentType
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetPublicKeyCredentialOption
import androidx.credentials.PublicKeyCredential
import androidx.credentials.exceptions.GetCredentialException
import androidx.fragment.app.FragmentActivity
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.ui.common.showBiometricPrompt
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    onNavigateToForgotPassword: () -> Unit,
    viewModel: AuthViewModel = hiltViewModel()
) {
    val loginState by viewModel.loginState.collectAsStateWithLifecycle()
    val passkeyOptionsState by viewModel.passkeyOptionsState.collectAsStateWithLifecycle()
    val navigateToHome by viewModel.navigateToHome.collectAsStateWithLifecycle()
    val showBiometricOffer by viewModel.showBiometricOffer.collectAsStateWithLifecycle()
    val focusManager = LocalFocusManager.current
    val context = LocalContext.current
    val activity = context as FragmentActivity
    val scope = rememberCoroutineScope()

    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passkeyError by remember { mutableStateOf<String?>(null) }
    var biometricError by remember { mutableStateOf<String?>(null) }

    val biometricLoginEnabled = remember { viewModel.isBiometricLoginEnabled() }

    // Navigation is driven exclusively by navigateToHome — no timing issues with other states
    LaunchedEffect(navigateToHome) {
        if (navigateToHome) {
            viewModel.resetNavigation()
            onLoginSuccess()
        }
    }

    LaunchedEffect(passkeyOptionsState) {
        if (passkeyOptionsState is UiState.Success) {
            val optionsJson = (passkeyOptionsState as UiState.Success).data
            viewModel.resetPasskeyOptionsState()
            scope.launch {
                try {
                    val credentialManager = CredentialManager.create(context)
                    val request = GetCredentialRequest(
                        listOf(GetPublicKeyCredentialOption(requestJson = optionsJson))
                    )
                    val result = credentialManager.getCredential(context, request)
                    val credential = result.credential
                    if (credential is PublicKeyCredential) {
                        viewModel.verifyPasskeyLogin(credential.authenticationResponseJson)
                    }
                } catch (e: GetCredentialException) {
                    passkeyError = e.message ?: "Passkey-innlogging ble avbrutt"
                }
            }
        }
    }

    // Biometric offer dialog — dismissBiometricOffer() and enableBiometricWithCipher()
    // both set navigateToHome = true, so navigation is handled automatically
    if (showBiometricOffer) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissBiometricOffer() },
            title = { Text("Logg inn med biometri?") },
            text = { Text("Neste gang kan du logge inn raskere med fingeravtrykk eller ansiktsgjenkjenning.") },
            confirmButton = {
                TextButton(onClick = {
                    try {
                        val cipher = viewModel.getCipherForEncryption()
                        showBiometricPrompt(
                            activity = activity,
                            title = "Bekreft biometri",
                            cipher = cipher,
                            onSuccess = { result ->
                                result.cryptoObject?.cipher?.let { viewModel.enableBiometricWithCipher(it) }
                            }
                            // onError: biometri-prompt avbrutt — dialog forblir åpen
                        )
                    } catch (e: Exception) {
                        viewModel.dismissBiometricOffer()
                    }
                }) { Text("Ja, aktiver") }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissBiometricOffer() }) { Text("Ikke nå") }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp)
            .imePadding(),
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
            text = "Logg inn på kontoen din",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(32.dp))

        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("E-post") },
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentType = ContentType.Username },
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            ),
            singleLine = true,
            isError = loginState is UiState.Error
        )
        Spacer(modifier = Modifier.height(12.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Passord") },
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentType = ContentType.Password },
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    if (email.isNotBlank() && password.isNotBlank()) {
                        viewModel.login(email, password)
                    }
                }
            ),
            singleLine = true,
            isError = loginState is UiState.Error
        )

        if (loginState is UiState.Error) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = (loginState as UiState.Error).message,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }
        if (passkeyError != null) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = passkeyError!!,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }
        if (biometricError != null) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = biometricError!!,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }

        Spacer(modifier = Modifier.height(8.dp))
        TextButton(
            onClick = onNavigateToForgotPassword,
            modifier = Modifier.align(Alignment.End)
        ) {
            Text("Glemt passord?")
        }

        Spacer(modifier = Modifier.height(8.dp))
        Button(
            onClick = { viewModel.login(email, password) },
            modifier = Modifier.fillMaxWidth(),
            enabled = email.isNotBlank() && password.isNotBlank() && loginState !is UiState.Loading
        ) {
            if (loginState is UiState.Loading) {
                CircularProgressIndicator(
                    modifier = Modifier.height(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text("Logg inn")
            }
        }

        Spacer(modifier = Modifier.height(8.dp))
        HorizontalDivider()
        Spacer(modifier = Modifier.height(8.dp))

        OutlinedButton(
            onClick = {
                passkeyError = null
                viewModel.getPasskeyOptions()
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = passkeyOptionsState !is UiState.Loading && loginState !is UiState.Loading
        ) {
            if (passkeyOptionsState is UiState.Loading) {
                CircularProgressIndicator(
                    modifier = Modifier.height(20.dp),
                    color = MaterialTheme.colorScheme.primary
                )
            } else {
                Text("Logg inn med passkey")
            }
        }

        if (biometricLoginEnabled) {
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    biometricError = null
                    val cipher = viewModel.getCipherForDecryption()
                    if (cipher == null) {
                        biometricError = "Biometri-data er ikke lenger gyldig. Logg inn med passord."
                        return@OutlinedButton
                    }
                    showBiometricPrompt(
                        activity = activity,
                        title = "Logg inn",
                        cipher = cipher,
                        onSuccess = { result ->
                            result.cryptoObject?.cipher?.let { viewModel.loginWithBiometricCipher(it) }
                        },
                        onError = { biometricError = it }
                    )
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = loginState !is UiState.Loading
            ) {
                Text("Logg inn med biometri")
            }
        }
    }
}
