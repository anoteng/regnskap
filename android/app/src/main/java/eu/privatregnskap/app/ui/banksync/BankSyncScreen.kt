package eu.privatregnskap.app.ui.banksync

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
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
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.bank.Sb1Api
import eu.privatregnskap.app.data.bank.Sb1Link
import eu.privatregnskap.app.data.bank.Sb1Status
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val DAY = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private val DAY_AND_TIME = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")

private fun Long.asLocal(formatter: DateTimeFormatter): String =
    Instant.ofEpochMilli(this).atZone(ZoneId.systemDefault()).format(formatter)

/** Norwegian account numbers are written 1234.56.78901. */
private fun String.asAccountNumber(): String =
    if (length == 11 && all(Char::isDigit)) "${take(4)}.${substring(4, 6)}.${substring(6)}" else this

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BankSyncScreen(
    innerPadding: PaddingValues,
    onBack: () -> Unit,
    viewModel: BankSyncViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val status by viewModel.status.collectAsStateWithLifecycle()
    val isSyncing by viewModel.isSyncing.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.openInBrowser.collect { url ->
            try {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            } catch (e: ActivityNotFoundException) {
                viewModel.browserMissing()
            }
        }
    }
    LaunchedEffect(state.message) {
        val message = state.message
        if (message != null) {
            // Consumed afterwards: clearing it first would restart this effect
            // and take the snackbar down with it
            snackbarHostState.showSnackbar(message)
            viewModel.consumeMessage()
        }
    }

    val loginUrl = state.loginUrl
    val draft = state.linkDraft
    val showLogin = status.hasClient && (!status.loggedIn || state.reLogin)

    // The back arrow first leaves whatever step is open, then the screen
    val inStep = loginUrl != null || draft != null || state.reLogin
    val leave: () -> Unit = {
        when {
            loginUrl != null -> viewModel.cancelLogin()
            draft != null -> viewModel.cancelLinking()
            state.reLogin -> viewModel.cancelNewLogin()
            else -> onBack()
        }
    }
    BackHandler(enabled = inStep, onBack = leave)

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        when {
                            loginUrl != null -> "Logg inn i banken"
                            draft != null -> "Koble til konto"
                            else -> "Banksynk fra denne enheten"
                        }
                    )
                },
                navigationIcon = {
                    IconButton(onClick = leave) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Tilbake")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { scaffoldPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(scaffoldPadding)
                .padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            when {
                state.isLoading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))

                loginUrl != null -> BankLoginWebView(
                    address = loginUrl,
                    onCallback = viewModel::onLoginCallback
                )

                else -> Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    val busy = state.busy
                    if (busy != null) {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                        Text(
                            text = busy,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    val error = state.error ?: status.lastError
                    if (error != null) {
                        Text(
                            text = error,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error
                        )
                    }

                    val idle = busy == null && !isSyncing
                    when {
                        draft != null -> LinkStep(draft, idle, viewModel)
                        !status.hasClient -> ClientKeysStep(idle, viewModel)
                        showLogin -> LoginStep(state, idle, viewModel)
                        else -> OverviewStep(status, state, idle, viewModel)
                    }
                }
            }
        }
    }
}

// ─── Step 1: the keys from the bank ──────────────────────────────────────────

@Composable
private fun ClientKeysStep(idle: Boolean, viewModel: BankSyncViewModel) {
    var clientId by rememberSaveable { mutableStateOf("") }
    // Not saveable: a secret has no business in the saved instance state
    var clientSecret by remember { mutableStateOf("") }

    Text(
        text = "Appen kan hente transaksjoner fra SpareBank 1 med din egen nøkkel fra banken, " +
            "og legge dem i posteringskøen. Det krever ikke Premium.",
        style = MaterialTheme.typography.bodyMedium
    )
    SectionTitle("Slik setter du det opp")
    Text(
        text = "1. Logg inn på developer.sparebank1.no med BankID og opprett en personlig klient.\n" +
            "2. Sett Redirect URI til adressen under.\n" +
            "3. Lim inn Client ID og Client Secret her.",
        style = MaterialTheme.typography.bodyMedium
    )
    SelectionContainer {
        Text(
            text = Sb1Api.REDIRECT_URI,
            style = MaterialTheme.typography.bodyMedium,
            fontFamily = FontFamily.Monospace
        )
    }
    OutlinedTextField(
        value = clientId,
        onValueChange = { clientId = it },
        label = { Text("Client ID") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    OutlinedTextField(
        value = clientSecret,
        onValueChange = { clientSecret = it },
        label = { Text("Client Secret") },
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        modifier = Modifier.fillMaxWidth()
    )
    Text(
        text = "Nøklene lagres kryptert på denne enheten og sendes aldri til Privatregnskap. " +
            "Banken gir dem til deg personlig; ikke del dem med andre.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    Button(
        onClick = { viewModel.saveClient(clientId, clientSecret) },
        enabled = idle,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text("Lagre nøklene")
    }
    Text(
        text = "Gjelder brukskontoer og sparekontoer. Kredittkort er ikke med ennå.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
}

// ─── Step 2: BankID ──────────────────────────────────────────────────────────

@Composable
private fun LoginStep(state: BankSyncUiState, idle: Boolean, viewModel: BankSyncViewModel) {
    var pasted by remember { mutableStateOf("") }
    var confirmRemove by remember { mutableStateOf(false) }

    Text(
        text = "Logg inn i banken med BankID. Innloggingen fornyes av seg selv så lenge appen " +
            "får synkronisere, og må gjøres på nytt etter ett år.",
        style = MaterialTheme.typography.bodyMedium
    )
    Button(
        onClick = viewModel::startLogin,
        enabled = idle,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text("Logg inn med BankID")
    }
    TextButton(onClick = viewModel::startBrowserLogin, enabled = idle) {
        Text("Åpne i nettleseren i stedet")
    }

    if (state.browserLogin) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "Fullfør innloggingen i nettleseren og kom tilbake hit. " +
                        "Viser nettleseren en feilside når du er ferdig, er det som ventet: " +
                        "kopier adressen fra adressefeltet og lim den inn her. " +
                        "Adressen virker i to minutter.",
                    style = MaterialTheme.typography.bodySmall
                )
                OutlinedTextField(
                    value = pasted,
                    onValueChange = { pasted = it },
                    label = { Text("Adressen fra nettleseren") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = { viewModel.submitPastedAddress(pasted) },
                    enabled = idle && pasted.isNotBlank()
                ) {
                    Text("Fullfør")
                }
            }
        }
    }

    TextButton(onClick = { confirmRemove = true }, enabled = idle) {
        Text("Fjern nøklene fra denne enheten", color = MaterialTheme.colorScheme.error)
    }

    if (confirmRemove) {
        RemoveKeysDialog(
            onConfirm = {
                confirmRemove = false
                viewModel.removeKeys()
            },
            onDismiss = { confirmRemove = false }
        )
    }
}

/**
 * The bank's login page inside the app.
 *
 * The bank ends the login by sending the browser to an address on this
 * device. That navigation is caught here and never loaded. Cookies and stored
 * data are thrown away when the view closes: the session at the bank is
 * carried by the refresh token alone.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun BankLoginWebView(address: String, onCallback: (String) -> Unit) {
    val currentOnCallback by rememberUpdatedState(onCallback)

    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                layoutParams = ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT
                )
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)

                // The redirect can show up in more than one callback. Once is enough.
                var delivered = false
                fun deliver(callback: String) {
                    if (!delivered) {
                        delivered = true
                        currentOnCallback(callback)
                    }
                }

                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                        val uri = request?.url ?: return false
                        if (isBankCallback(uri)) {
                            deliver(uri.toString())
                            return true
                        }
                        val scheme = uri.scheme?.lowercase()
                        if (scheme == "http" || scheme == "https") return false
                        // The BankID app and its like: hand over to whoever owns the address
                        openOutside(context, uri)
                        return true
                    }

                    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                        if (url != null && isBankCallback(Uri.parse(url))) {
                            view?.stopLoading()
                            deliver(url)
                        }
                    }

                    override fun onReceivedError(
                        view: WebView?,
                        request: WebResourceRequest?,
                        error: WebResourceError?
                    ) {
                        val uri = request?.url ?: return
                        if (isBankCallback(uri)) deliver(uri.toString())
                    }
                }
                loadUrl(address)
            }
        },
        onRelease = { webView ->
            webView.stopLoading()
            webView.destroy()
            CookieManager.getInstance().removeAllCookies(null)
            WebStorage.getInstance().deleteAllData()
        }
    )
}

private fun isBankCallback(uri: Uri): Boolean =
    uri.scheme == "http" &&
        uri.host == "localhost" &&
        uri.port == Sb1Api.REDIRECT_PORT &&
        uri.path == Sb1Api.REDIRECT_PATH

private fun openOutside(context: Context, uri: Uri) {
    try {
        val intent = if (uri.scheme == "intent") {
            // An intent address may name any component it likes. Only let it
            // reach what a browser could have reached.
            Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME).apply {
                addCategory(Intent.CATEGORY_BROWSABLE)
                component = null
                selector = null
            }
        } else {
            Intent(Intent.ACTION_VIEW, uri)
        }
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (e: Exception) {
        // Nothing on the device takes the address. The page stays where it is.
    }
}

// ─── Step 3: accounts and sync ───────────────────────────────────────────────

@Composable
private fun OverviewStep(
    status: Sb1Status,
    state: BankSyncUiState,
    idle: Boolean,
    viewModel: BankSyncViewModel
) {
    var confirmRemove by remember { mutableStateOf(false) }
    var unlinkTarget by remember { mutableStateOf<Sb1Link?>(null) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(
                text = status.loginAt?.let { "Innlogget i banken siden ${it.asLocal(DAY)}" }
                    ?: "Innlogget i banken",
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = status.lastSyncAt?.let { "Sist synkronisert ${it.asLocal(DAY_AND_TIME)}" }
                    ?: "Ikke synkronisert ennå",
                style = MaterialTheme.typography.bodyMedium
            )
            status.lastSyncMessage?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }

    Button(
        onClick = viewModel::syncNow,
        enabled = idle && status.links.isNotEmpty(),
        modifier = Modifier.fillMaxWidth()
    ) {
        Text("Synkroniser nå")
    }

    SectionTitle("Kontoer")
    if (status.links.isEmpty()) {
        Text(
            text = "Ingen kontoer er koblet til ennå.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
    status.links.forEach { link ->
        val trouble = when {
            link.connectionId in state.missingConnections ->
                "Koblingen finnes ikke lenger i regnskapet. Fjern den og koble til på nytt."
            else -> state.serverErrors[link.connectionId]
        }
        Card(modifier = Modifier.fillMaxWidth()) {
            ListItem(
                headlineContent = { Text(link.accountName) },
                supportingContent = {
                    Column {
                        Text("${link.accountNumber.asAccountNumber()} → ${link.bankAccountName}")
                        if (trouble != null) {
                            Text(trouble, color = MaterialTheme.colorScheme.error)
                        }
                    }
                },
                trailingContent = {
                    IconButton(onClick = { unlinkTarget = link }, enabled = idle) {
                        Icon(Icons.Default.Delete, contentDescription = "Koble fra")
                    }
                }
            )
        }
    }
    OutlinedButton(
        onClick = viewModel::startLinking,
        enabled = idle,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text("Legg til konto")
    }

    Text(
        text = "Appen synkroniserer av seg selv to ganger i døgnet. Nye transaksjoner havner i " +
            "posteringskøen. Blir enheten stille i to uker, får du en e-post om det.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )

    TextButton(onClick = viewModel::askForNewLogin, enabled = idle) {
        Text("Logg inn i banken på nytt")
    }
    TextButton(onClick = { confirmRemove = true }, enabled = idle) {
        Text("Fjern nøklene fra denne enheten", color = MaterialTheme.colorScheme.error)
    }

    if (confirmRemove) {
        RemoveKeysDialog(
            onConfirm = {
                confirmRemove = false
                viewModel.removeKeys()
            },
            onDismiss = { confirmRemove = false }
        )
    }

    unlinkTarget?.let { link ->
        AlertDialog(
            onDismissRequest = { unlinkTarget = null },
            title = { Text("Koble fra ${link.accountName}?") },
            text = {
                Text(
                    "Appen slutter å hente transaksjoner for kontoen. Det som allerede er hentet, " +
                        "blir liggende i regnskapet."
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    unlinkTarget = null
                    viewModel.unlink(link)
                }) {
                    Text("Koble fra")
                }
            },
            dismissButton = {
                TextButton(onClick = { unlinkTarget = null }) { Text("Avbryt") }
            }
        )
    }
}

@Composable
private fun RemoveKeysDialog(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Fjerne nøklene?") },
        text = {
            Text(
                "Nøklene, innloggingen i banken og kontokoblingene fjernes fra denne enheten, " +
                    "og synkroniseringen stopper. Transaksjonene som er hentet, blir liggende i " +
                    "regnskapet. Klienten hos banken sletter du selv på developer.sparebank1.no."
            )
        },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
            ) {
                Text("Fjern")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Avbryt") }
        }
    )
}

// ─── Linking an account ──────────────────────────────────────────────────────

@Composable
private fun LinkStep(draft: LinkDraft, idle: Boolean, viewModel: BankSyncViewModel) {
    Text(
        text = "Velg en konto i banken og bankkontoen den hører til i regnskapet" +
            (draft.ledgerName?.let { " «$it»." } ?: "."),
        style = MaterialTheme.typography.bodyMedium
    )

    SectionTitle("Konto i banken")
    if (draft.accounts.isEmpty()) {
        Text(
            text = "Banken viser ingen kontoer som ikke allerede er koblet til.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
    draft.accounts.forEach { account ->
        ChoiceRow(
            selected = draft.account?.accountNumber == account.accountNumber,
            title = account.name,
            subtitle = account.accountNumber.asAccountNumber(),
            onSelect = { viewModel.selectAccount(account) }
        )
    }

    SectionTitle("Bankkonto i regnskapet")
    if (draft.ledgerAccounts.isEmpty()) {
        Text(
            text = "Regnskapet har ingen ledige bankkontoer. Opprett en først.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error
        )
    }
    draft.ledgerAccounts.forEach { ledgerAccount ->
        ChoiceRow(
            selected = draft.ledgerAccountId == ledgerAccount.id,
            title = ledgerAccount.name,
            subtitle = ledgerAccount.accountNumber?.asAccountNumber(),
            onSelect = { viewModel.selectLedgerAccount(ledgerAccount.id) }
        )
    }

    SectionTitle("Hent transaksjoner fra de siste")
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        SyncHistory.entries.forEach { history ->
            FilterChip(
                selected = draft.history == history,
                onClick = { viewModel.selectHistory(history) },
                label = { Text(history.label) }
            )
        }
    }
    Text(
        text = "Har kontoen vært synkronisert på en annen måte, velg en periode som begynner " +
            "etter den siste synkroniseringen. Ellers kommer de samme transaksjonene inn en gang til.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )

    Button(
        onClick = viewModel::confirmLink,
        enabled = idle && draft.account != null && draft.ledgerAccountId != null,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text("Koble til")
    }
}

@Composable
private fun ChoiceRow(selected: Boolean, title: String, subtitle: String?, onSelect: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect)
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        RadioButton(selected = selected, onClick = null)
        Column(modifier = Modifier.padding(start = 12.dp)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            if (!subtitle.isNullOrBlank()) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp)
    )
}
