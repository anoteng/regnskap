package eu.privatregnskap.app.ui.ledger

import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * Creates a ledger. Doubles as onboarding: when the user has no ledgers at all
 * there is nothing to go back to, so [onBack] is omitted in that case.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreateLedgerScreen(
    innerPadding: PaddingValues,
    onCreated: () -> Unit,
    onBack: (() -> Unit)? = null,
    viewModel: CreateLedgerViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(state.createdLedgerId) {
        if (state.createdLedgerId != null) onCreated()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (onBack == null) "Opprett ditt første regnskap" else "Nytt regnskap") },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Tilbake")
                        }
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

                state.templates.isEmpty() -> Column(
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = state.error ?: "Fant ingen kontoplaner",
                        color = MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.loadTemplates() }) { Text("Prøv igjen") }
                }

                else -> CreateForm(state = state, viewModel = viewModel)
            }
        }
    }
}

@Composable
private fun CreateForm(state: CreateLedgerUiState, viewModel: CreateLedgerViewModel) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        item {
            SectionTitle("Kontoplan")
            Text(
                text = "Bestemmer hvilke kontoer regnskapet starter med. Du kan endre kontoplanen senere.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
        }

        items(state.templates, key = { it.id }) { template ->
            val selected = template.id == state.selectedTemplateId
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .border(
                        width = if (selected) 2.dp else 1.dp,
                        color = if (selected) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.outlineVariant,
                        shape = RoundedCornerShape(8.dp)
                    )
                    .clickable { viewModel.selectTemplate(template.id) }
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                RadioButton(
                    selected = selected,
                    onClick = { viewModel.selectTemplate(template.id) }
                )
                Column(modifier = Modifier.weight(1f)) {
                    Text(template.displayName, style = MaterialTheme.typography.bodyLarge)
                    template.description?.takeIf { it.isNotBlank() }?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }

        item {
            SectionTitle("Navn")
            OutlinedTextField(
                value = state.name,
                onValueChange = { viewModel.setName(it) },
                label = { Text("Navn på regnskapet") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
            )
        }

        item {
            SectionTitle("Bankkontoer (valgfritt)")
            Text(
                text = "Kontoene du fører regnskap for. Automatisk banksynkronisering settes opp " +
                    "i nettversjonen — her oppretter du bare kontoene.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
        }

        items(state.bankAccounts, key = { it.id }) { account ->
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = account.name,
                        onValueChange = { viewModel.setBankAccountName(account.id, it) },
                        label = { Text("Kontonavn") },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { viewModel.removeBankAccount(account.id) }) {
                        Icon(Icons.Default.Close, contentDescription = "Fjern konto")
                    }
                }
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(top = 4.dp)
                ) {
                    BANK_ACCOUNT_TYPES.forEach { (value, label) ->
                        FilterChip(
                            selected = account.accountType == value,
                            onClick = { viewModel.setBankAccountType(account.id, value) },
                            label = { Text(label) }
                        )
                    }
                }
            }
        }

        item {
            TextButton(
                onClick = { viewModel.addBankAccount() },
                modifier = Modifier.padding(horizontal = 8.dp)
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(modifier = Modifier.width(4.dp))
                Text("Legg til bankkonto")
            }
        }

        item {
            state.error?.let { error ->
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
            }
            Button(
                onClick = { viewModel.create() },
                enabled = state.canSubmit,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Text(if (state.isSaving) "Oppretter…" else "Opprett regnskap")
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
        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp)
    )
}
