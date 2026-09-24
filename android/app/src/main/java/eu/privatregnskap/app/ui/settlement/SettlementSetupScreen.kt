package eu.privatregnskap.app.ui.settlement

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.AccountResponse
import kotlin.math.abs

private sealed interface AccountPicker {
    object Operating : AccountPicker
    data class Deposit(val userId: Int) : AccountPicker
}

private fun accountLabel(accounts: List<AccountResponse>, id: Int?): String {
    if (id == null) return "Ikke valgt"
    val account = accounts.firstOrNull { it.id == id } ?: return "Konto #$id"
    return "${account.accountNumber} ${account.accountName}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettlementSetupScreen(
    innerPadding: PaddingValues,
    onBack: () -> Unit,
    onSaved: () -> Unit,
    viewModel: SettlementSetupViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var picker by remember { mutableStateOf<AccountPicker?>(null) }
    var excludeQuery by remember { mutableStateOf("") }

    LaunchedEffect(state.saved) {
        if (state.saved) {
            viewModel.consumeSaved()
            onSaved()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Sett opp avregning") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Tilbake")
                    }
                }
            )
        }
    ) { scaffoldPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(scaffoldPadding)
                .padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            when {
                state.isLoading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))

                state.loadError != null -> Text(
                    text = state.loadError!!,
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.align(Alignment.Center).padding(24.dp)
                )

                else -> SetupForm(
                    state = state,
                    excludeQuery = excludeQuery,
                    onExcludeQueryChange = { excludeQuery = it },
                    onPick = { picker = it },
                    viewModel = viewModel
                )
            }
        }
    }

    when (val active = picker) {
        null -> Unit
        is AccountPicker.Operating -> AccountPickerSheet(
            title = "Velg driftskonto",
            accounts = state.assetAccounts,
            selectedId = state.operatingAccountId,
            onPick = { viewModel.setOperatingAccount(it); picker = null },
            onDismiss = { picker = null }
        )
        is AccountPicker.Deposit -> AccountPickerSheet(
            title = "Velg innskuddskonto",
            accounts = state.depositCandidates,
            selectedId = state.members.firstOrNull { it.userId == active.userId }?.depositAccountId,
            onPick = { viewModel.setDepositAccount(active.userId, it); picker = null },
            onDismiss = { picker = null }
        )
    }
}

@Composable
private fun SetupForm(
    state: SettlementSetupUiState,
    excludeQuery: String,
    onExcludeQueryChange: (String) -> Unit,
    onPick: (AccountPicker) -> Unit,
    viewModel: SettlementSetupViewModel
) {
    val enabled = state.canEdit
    val shareSum = state.shareSum
    val sharesOk = abs(shareSum - 100.0) < 0.01

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        item {
            Text(
                text = "Avregningen viser hvor mye hver deltaker bør overføre til driftskontoen " +
                    "denne måneden, ut fra bokførte kostnader, registrerte fakturaer, faste trekk " +
                    "fra historikken og et anslag for variable kostnader.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp)
            )
            if (!state.canEdit) {
                Text(
                    text = "Bare eieren av regnskapet kan endre disse innstillingene.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp)
                )
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Aktiver månedsavregning", modifier = Modifier.weight(1f))
                Switch(
                    checked = state.isEnabled,
                    onCheckedChange = { viewModel.setEnabled(it) },
                    enabled = enabled
                )
            }
        }

        item {
            ListItem(
                headlineContent = { Text("Driftskonto") },
                supportingContent = {
                    Text(accountLabel(state.accounts, state.operatingAccountId))
                },
                modifier = Modifier.clickable(enabled = enabled) { onPick(AccountPicker.Operating) }
            )
            Text(
                text = "Kontoen felleskostnadene betales fra.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Måneder historikk for variable kostnader", modifier = Modifier.weight(1f))
                IconButton(
                    onClick = { viewModel.setLookbackMonths(state.lookbackMonths - 1) },
                    enabled = enabled && state.lookbackMonths > 1
                ) { Icon(Icons.Default.Remove, contentDescription = "Færre måneder") }
                Text(state.lookbackMonths.toString(), style = MaterialTheme.typography.titleMedium)
                IconButton(
                    onClick = { viewModel.setLookbackMonths(state.lookbackMonths + 1) },
                    enabled = enabled && state.lookbackMonths < 24
                ) { Icon(Icons.Default.Add, contentDescription = "Flere måneder") }
            }
            HorizontalDivider()
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 16.dp, end = 8.dp, top = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Deltakere",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.weight(1f)
                )
                TextButton(onClick = { viewModel.distributeEvenly() }, enabled = enabled) {
                    Text("Fordel likt")
                }
            }
        }

        items(state.members, key = { it.userId }) { member ->
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(member.name, style = MaterialTheme.typography.bodyLarge)
                Text(
                    member.email,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = member.sharePercent,
                        onValueChange = { viewModel.setShare(member.userId, it) },
                        label = { Text("Andel %") },
                        singleLine = true,
                        enabled = enabled,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        modifier = Modifier.width(120.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clickable(enabled = enabled) { onPick(AccountPicker.Deposit(member.userId)) }
                    ) {
                        Text(
                            "Innskuddskonto",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(accountLabel(state.accounts, member.depositAccountId))
                    }
                }
            }
        }

        item {
            Text(
                text = if (sharesOk) "Andelene summerer til 100 %."
                       else "Andelene summerer til ${formatPercent(shareSum)} % — må bli 100 % for å aktivere.",
                style = MaterialTheme.typography.bodySmall,
                color = if (sharesOk) MaterialTheme.colorScheme.onSurfaceVariant
                        else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
            Text(
                text = "Innskuddskontoen er der deltakerens innbetalinger krediteres og egne uttak " +
                    "fra driftskontoen debiteres. La den stå tom hvis det ikke er aktuelt.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
            HorizontalDivider(modifier = Modifier.padding(top = 12.dp))
        }

        item {
            Text(
                text = "Kostnadskontoer som holdes utenfor",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp)
            )
            Text(
                text = "Kostnader ført her regnes ikke som felleskostnader — for eksempel utlegg " +
                    "som refunderes, eller investeringer én deltaker dekker selv.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
            OutlinedTextField(
                value = excludeQuery,
                onValueChange = onExcludeQueryChange,
                label = { Text("Søk i kontoplanen") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            )
        }

        val visible = state.expenseAccounts.filter {
            excludeQuery.isBlank() ||
                "${it.accountNumber} ${it.accountName}".contains(excludeQuery, ignoreCase = true)
        }
        items(visible, key = { it.id }) { account ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(enabled = enabled) { viewModel.toggleExcluded(account.id) }
                    .padding(horizontal = 16.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(
                    checked = account.id in state.excludedAccountIds,
                    onCheckedChange = { viewModel.toggleExcluded(account.id) },
                    enabled = enabled
                )
                Text(
                    text = "${account.accountNumber} ${account.accountName}",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }

        item {
            state.saveError?.let { error ->
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
            }
            Button(
                onClick = { viewModel.save() },
                enabled = enabled && !state.isSaving,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Text(if (state.isSaving) "Lagrer…" else "Lagre innstillinger")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AccountPickerSheet(
    title: String,
    accounts: List<AccountResponse>,
    selectedId: Int?,
    onPick: (Int?) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    val visible = accounts.filter {
        query.isBlank() || "${it.accountNumber} ${it.accountName}".contains(query, ignoreCase = true)
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            )
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Søk") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
            )
            LazyColumn(modifier = Modifier.fillMaxWidth()) {
                item {
                    ListItem(
                        headlineContent = { Text("Ingen konto") },
                        modifier = Modifier.clickable { onPick(null) }
                    )
                    HorizontalDivider()
                }
                items(visible, key = { it.id }) { account ->
                    ListItem(
                        headlineContent = {
                            Text(
                                text = "${account.accountNumber} ${account.accountName}",
                                fontWeight = if (account.id == selectedId) FontWeight.Bold else FontWeight.Normal
                            )
                        },
                        modifier = Modifier.clickable { onPick(account.id) }
                    )
                }
            }
        }
    }
}

private fun formatPercent(value: Double): String =
    if (value == value.toLong().toDouble()) value.toLong().toString()
    else String.format("%.2f", value)
