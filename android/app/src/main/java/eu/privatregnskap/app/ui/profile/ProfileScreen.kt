package eu.privatregnskap.app.ui.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.Switch
import androidx.core.content.ContextCompat
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.credentials.CreatePublicKeyCredentialRequest
import androidx.credentials.CreatePublicKeyCredentialResponse
import androidx.credentials.CredentialManager
import androidx.credentials.exceptions.CreateCredentialException
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.PasskeyCredentialResponse
import eu.privatregnskap.app.ui.auth.AuthViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    onLogout: () -> Unit,
    authViewModel: AuthViewModel = hiltViewModel(),
    profileViewModel: ProfileViewModel = hiltViewModel()
) {
    val credentials by profileViewModel.credentials.collectAsStateWithLifecycle()
    val isLoading by profileViewModel.isLoading.collectAsStateWithLifecycle()
    val registerOptionsState by profileViewModel.registerOptionsState.collectAsStateWithLifecycle()
    val queueNotificationsEnabled by profileViewModel.queueNotificationsEnabled.collectAsStateWithLifecycle()

    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) profileViewModel.setQueueNotificationsEnabled(true)
    }

    var deleteConfirmId by remember { mutableStateOf<Int?>(null) }
    var renameTarget by remember { mutableStateOf<PasskeyCredentialResponse?>(null) }
    var renameText by remember { mutableStateOf("") }
    var addNameDialog by remember { mutableStateOf(false) }
    var newPasskeyName by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        profileViewModel.message.collect { msg ->
            snackbarHostState.showSnackbar(msg)
        }
    }

    // When registration options are ready, trigger CredentialManager
    LaunchedEffect(registerOptionsState) {
        if (registerOptionsState is RegisterOptionsState.Ready) {
            val optionsJson = (registerOptionsState as RegisterOptionsState.Ready).optionsJson
            profileViewModel.resetRegisterOptionsState()
            scope.launch {
                try {
                    val credentialManager = CredentialManager.create(context)
                    val request = CreatePublicKeyCredentialRequest(requestJson = optionsJson)
                    val result = credentialManager.createCredential(context, request)
                    if (result is CreatePublicKeyCredentialResponse) {
                        profileViewModel.completeRegistration(result.registrationResponseJson)
                    }
                } catch (e: CreateCredentialException) {
                    snackbarHostState.showSnackbar(e.message ?: "Passkey-registrering ble avbrutt")
                }
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Profil") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Text("Innstillinger", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(4.dp))
                Card(modifier = Modifier.fillMaxWidth()) {
                    ListItem(
                        headlineContent = { Text("Varsler om posteringskø") },
                        supportingContent = { Text("Varsle om nye transaksjoner i posteringskøen") },
                        leadingContent = {
                            Icon(Icons.Default.Notifications, contentDescription = null)
                        },
                        trailingContent = {
                            Switch(
                                checked = queueNotificationsEnabled,
                                onCheckedChange = { enabled ->
                                    if (enabled) {
                                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                            val granted = ContextCompat.checkSelfPermission(
                                                context, Manifest.permission.POST_NOTIFICATIONS
                                            ) == PackageManager.PERMISSION_GRANTED
                                            if (granted) {
                                                profileViewModel.setQueueNotificationsEnabled(true)
                                            } else {
                                                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                                            }
                                        } else {
                                            profileViewModel.setQueueNotificationsEnabled(true)
                                        }
                                    } else {
                                        profileViewModel.setQueueNotificationsEnabled(false)
                                    }
                                }
                            )
                        }
                    )
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Passkeys", style = MaterialTheme.typography.titleMedium)
                    IconButton(onClick = { addNameDialog = true }) {
                        Icon(Icons.Default.Add, contentDescription = "Legg til passkey")
                    }
                }
            }

            if (isLoading) {
                item {
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(modifier = Modifier.size(32.dp))
                    }
                }
            } else if (credentials.isEmpty()) {
                item {
                    Text(
                        "Ingen passkeys registrert",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }
            } else {
                items(credentials, key = { it.id }) { cred ->
                    PasskeyItem(
                        credential = cred,
                        onDelete = { deleteConfirmId = cred.id },
                        onRename = {
                            renameTarget = cred
                            renameText = cred.credentialName ?: ""
                        }
                    )
                }
            }

            item {
                Spacer(modifier = Modifier.height(16.dp))
                OutlinedButton(
                    onClick = { addNameDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = registerOptionsState !is RegisterOptionsState.Loading
                ) {
                    if (registerOptionsState is RegisterOptionsState.Loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp))
                    } else {
                        Icon(Icons.Default.Key, contentDescription = null)
                        Spacer(modifier = Modifier.size(8.dp))
                        Text("Legg til passkey")
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
                Button(
                    onClick = {
                        authViewModel.logout()
                        onLogout()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Logg ut")
                }
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }

    // Delete confirmation dialog
    if (deleteConfirmId != null) {
        AlertDialog(
            onDismissRequest = { deleteConfirmId = null },
            title = { Text("Slett passkey") },
            text = { Text("Er du sikker på at du vil slette denne passkeyen?") },
            confirmButton = {
                TextButton(onClick = {
                    profileViewModel.deleteCredential(deleteConfirmId!!)
                    deleteConfirmId = null
                }) { Text("Slett", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { deleteConfirmId = null }) { Text("Avbryt") }
            }
        )
    }

    // Rename dialog
    if (renameTarget != null) {
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text("Gi nytt navn") },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    label = { Text("Navn") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        profileViewModel.renameCredential(renameTarget!!.id, renameText.trim())
                        renameTarget = null
                    },
                    enabled = renameText.isNotBlank()
                ) { Text("Lagre") }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) { Text("Avbryt") }
            }
        )
    }

    // Add passkey name dialog
    if (addNameDialog) {
        AlertDialog(
            onDismissRequest = { addNameDialog = false },
            title = { Text("Legg til passkey") },
            text = {
                Column {
                    Text(
                        "Gi passkeyen et navn (valgfritt):",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = newPasskeyName,
                        onValueChange = { newPasskeyName = it },
                        label = { Text("Navn (f.eks. Telefon)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    addNameDialog = false
                    profileViewModel.beginRegistration(newPasskeyName.trim().ifBlank { null })
                    newPasskeyName = ""
                }) { Text("Fortsett") }
            },
            dismissButton = {
                TextButton(onClick = {
                    addNameDialog = false
                    newPasskeyName = ""
                }) { Text("Avbryt") }
            }
        )
    }
}

@Composable
private fun PasskeyItem(
    credential: PasskeyCredentialResponse,
    onDelete: () -> Unit,
    onRename: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        ListItem(
            headlineContent = {
                Text(credential.credentialName ?: "Passkey #${credential.id}")
            },
            supportingContent = {
                Text(
                    "Opprettet: ${credential.createdAt.take(10)}" +
                        (credential.lastUsedAt?.let { " · Sist brukt: ${it.take(10)}" } ?: ""),
                    style = MaterialTheme.typography.bodySmall
                )
            },
            leadingContent = {
                Icon(Icons.Default.Key, contentDescription = null)
            },
            trailingContent = {
                Row {
                    IconButton(onClick = onRename) {
                        Icon(Icons.Default.Edit, contentDescription = "Gi nytt navn")
                    }
                    IconButton(onClick = onDelete) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = "Slett",
                            tint = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
        )
    }
}
