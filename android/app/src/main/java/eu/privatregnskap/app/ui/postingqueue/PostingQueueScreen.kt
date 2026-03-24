package eu.privatregnskap.app.ui.postingqueue

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.ChainSuggestionDto
import eu.privatregnskap.app.data.network.dto.JournalEntryUpdate
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.network.dto.UpdateTransactionRequest

// ─── State for journal entry editing ──────────────────────────────────────────

data class EditEntryState(
    val id: Int,          // journal entry id (negative for new entries)
    val accountId: Int? = null,
    val accountNumber: String = "",
    val accountName: String = "",
    val debit: String = "0.00",
    val credit: String = "0.00"
)

private var newEntryCounter = -1
private fun nextEntryId() = newEntryCounter--

// ─── Helper functions ──────────────────────────────────────────────────────────

fun formatAmount(amount: Double): String = String.format(java.util.Locale.US, "%.2f kr", amount)

private fun parseAmount(s: String): Double = s.replace(',', '.').toDoubleOrNull() ?: 0.0
private fun formatEntry(value: Double): String = String.format(java.util.Locale.US, "%.2f", value)

@Composable
private fun SourceBadge(source: String?) {
    val (text, containerColor) = when (source) {
        "CSV_IMPORT" -> "CSV" to MaterialTheme.colorScheme.secondaryContainer
        "BANK_SYNC" -> "Bank" to MaterialTheme.colorScheme.tertiaryContainer
        else -> "Manuell" to MaterialTheme.colorScheme.surfaceVariant
    }
    Surface(
        shape = MaterialTheme.shapes.extraSmall,
        color = containerColor
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

// ─── Main screen ──────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PostingQueueScreen(
    innerPadding: PaddingValues = PaddingValues(),
    viewModel: PostingQueueViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val accounts by viewModel.accounts.collectAsStateWithLifecycle()
    val chainSuggestions by viewModel.chainSuggestions.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.message.collect { msg ->
            snackbarHostState.showSnackbar(msg)
        }
    }

    var expandedId by remember { mutableStateOf<Int?>(null) }
    var editingTransaction by remember { mutableStateOf<TransactionResponse?>(null) }
    var deletingId by remember { mutableStateOf<Int?>(null) }

    val balancedCount = uiState.transactions.count { it.isBalanced() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (uiState.total > 0) "Posteringskø (${uiState.total})"
                        else "Posteringskø"
                    )
                },
                actions = {
                    if (balancedCount > 0) {
                        TextButton(onClick = { viewModel.postAllTransactions() }) {
                            Text("Poster $balancedCount")
                        }
                    }
                    IconButton(onClick = { viewModel.loadAll() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Last på nytt")
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
                uiState.isLoading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                uiState.error != null -> {
                    Text(
                        text = uiState.error!!,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(24.dp)
                    )
                }
                uiState.transactions.isEmpty() -> {
                    Column(
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(48.dp)
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Ingen transaksjoner i kø",
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
                else -> {
                    LazyColumn(modifier = Modifier.fillMaxSize()) {
                        items(uiState.transactions, key = { it.id }) { transaction ->
                            TransactionQueueCard(
                                transaction = transaction,
                                isExpanded = expandedId == transaction.id,
                                onToggleExpand = {
                                    expandedId =
                                        if (expandedId == transaction.id) null else transaction.id
                                },
                                onPost = { viewModel.postTransaction(transaction.id) },
                                onEdit = { editingTransaction = transaction },
                                onDelete = { deletingId = transaction.id }
                            )
                        }
                    }
                }
            }
        }
    }

    // Delete confirmation
    deletingId?.let { id ->
        AlertDialog(
            onDismissRequest = { deletingId = null },
            title = { Text("Slett transaksjon") },
            text = { Text("Er du sikker på at du vil slette denne transaksjonen?") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.deleteTransaction(id)
                    deletingId = null
                }) {
                    Text("Slett", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { deletingId = null }) { Text("Avbryt") }
            }
        )
    }

    // Edit bottom sheet
    editingTransaction?.let { transaction ->
        val txSuggestions = chainSuggestions.filter {
            it.primaryTransactionId == transaction.id || it.secondaryTransactionId == transaction.id
        }
        EditTransactionSheet(
            transaction = transaction,
            accounts = accounts,
            chainSuggestions = txSuggestions,
            otherTransactions = uiState.transactions.filter { it.id != transaction.id },
            onDismiss = { editingTransaction = null },
            onSave = { request ->
                viewModel.updateTransaction(transaction.id, request)
                editingTransaction = null
            },
            onChain = { otherId, autoPost ->
                viewModel.chainTransactions(transaction.id, otherId, autoPost)
                editingTransaction = null
            }
        )
    }
}

// ─── Transaction card ──────────────────────────────────────────────────────────

@Composable
private fun TransactionQueueCard(
    transaction: TransactionResponse,
    isExpanded: Boolean,
    onToggleExpand: () -> Unit,
    onPost: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    val balanced = transaction.isBalanced()
    val totalDebit = transaction.journalEntries.sumOf { it.debit ?: 0.0 }
    val totalCredit = transaction.journalEntries.sumOf { it.credit ?: 0.0 }
    val amount = transaction.totalAmount()

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column {
            // Header — always visible
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggleExpand)
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = if (balanced) Icons.Default.CheckCircle else Icons.Default.Warning,
                    contentDescription = null,
                    tint = if (balanced) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = transaction.description,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Text(
                            text = transaction.transactionDate,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        SourceBadge(transaction.source)
                    }
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    text = formatAmount(amount),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium
                )
                Spacer(Modifier.width(4.dp))
                Icon(
                    imageVector = if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(20.dp)
                )
            }

            // Expanded content
            AnimatedVisibility(visible = isExpanded) {
                Column {
                    HorizontalDivider()

                    // Journal entries
                    transaction.journalEntries.forEach { entry ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp, vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = entry.displayName(),
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.weight(1f),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            if ((entry.debit ?: 0.0) > 0.001) {
                                Text(
                                    text = "D: ${formatAmount(entry.debit ?: 0.0)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            if ((entry.credit ?: 0.0) > 0.001) {
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = "K: ${formatAmount(entry.credit ?: 0.0)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error
                                )
                            }
                        }
                    }

                    if (!balanced) {
                        val diff = kotlin.math.abs(totalDebit - totalCredit)
                        Text(
                            text = if (transaction.journalEntries.size < 2)
                                "Legg til motposter i Rediger"
                            else "Ikke balansert — diff: ${formatAmount(diff)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                        )
                    }

                    HorizontalDivider()

                    // Action buttons
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 8.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        if (balanced) {
                            Button(
                                onClick = onPost,
                                modifier = Modifier.weight(1f)
                            ) { Text("Poster") }
                        }
                        OutlinedButton(
                            onClick = onEdit,
                            modifier = Modifier.weight(1f)
                        ) { Text("Rediger") }
                        OutlinedButton(
                            onClick = onDelete,
                            modifier = Modifier.weight(if (balanced) 1f else 0.8f),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = MaterialTheme.colorScheme.error
                            ),
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error)
                        ) { Text("Slett") }
                    }
                }
            }
        }
    }
}

// ─── Edit bottom sheet ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EditTransactionSheet(
    transaction: TransactionResponse,
    accounts: List<AccountResponse>,
    chainSuggestions: List<ChainSuggestionDto>,
    otherTransactions: List<TransactionResponse>,
    onDismiss: () -> Unit,
    onSave: (UpdateTransactionRequest) -> Unit,
    onChain: (Int, Boolean) -> Unit
) {
    var date by remember { mutableStateOf(transaction.transactionDate) }
    var description by remember { mutableStateOf(transaction.description) }
    var reference by remember { mutableStateOf(transaction.reference ?: "") }

    val entries = remember {
        mutableStateListOf(*transaction.journalEntries.map { entry ->
            EditEntryState(
                id = entry.id,
                accountId = entry.accountId,
                accountNumber = entry.account?.accountNumber ?: "",
                accountName = entry.account?.accountName ?: "",
                debit = if ((entry.debit ?: 0.0) > 0.001) formatEntry(entry.debit!!) else "0.00",
                credit = if ((entry.credit ?: 0.0) > 0.001) formatEntry(entry.credit!!) else "0.00"
            )
        }.toTypedArray())
    }

    var showChainPicker by remember { mutableStateOf(false) }

    val totalDebit = entries.sumOf { parseAmount(it.debit) }
    val totalCredit = entries.sumOf { parseAmount(it.credit) }
    val diff = kotlin.math.abs(totalDebit - totalCredit)
    val balanced = diff < 0.01 && entries.size >= 2
    val allAccountsValid = entries.all { it.accountId != null }
    val canSave = balanced && allAccountsValid

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp)
        ) {
            Text("Rediger transaksjon", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = date,
                onValueChange = { date = it },
                label = { Text("Dato") },
                placeholder = { Text("ÅÅÅÅ-MM-DD") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value = description,
                onValueChange = { description = it },
                label = { Text("Beskrivelse") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value = reference,
                onValueChange = { reference = it },
                label = { Text("Referanse (valgfritt)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(Modifier.height(16.dp))

            Text("Posteringer", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))

            entries.forEachIndexed { idx, entry ->
                key(entry.id) {
                    JournalEntryEditor(
                        entry = entry,
                        accounts = accounts,
                        canRemove = entries.size > 1,
                        onUpdate = { updated -> entries[idx] = updated },
                        onRemove = { entries.removeAt(idx) }
                    )
                    Spacer(Modifier.height(8.dp))
                }
            }

            // Inline balance status — visible without scrolling past keyboard
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = if (balanced)
                        MaterialTheme.colorScheme.secondaryContainer
                    else
                        MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            "D: ${formatAmount(totalDebit)}  K: ${formatAmount(totalCredit)}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Icon(
                            imageVector = if (balanced) Icons.Default.CheckCircle else Icons.Default.Warning,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = if (balanced)
                                MaterialTheme.colorScheme.onSecondaryContainer
                            else
                                MaterialTheme.colorScheme.onErrorContainer
                        )
                        Text(
                            text = if (balanced) "Balansert"
                            else "Diff: ${formatAmount(diff)}",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = if (balanced)
                                MaterialTheme.colorScheme.onSecondaryContainer
                            else
                                MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // Pre-fill balance difference for new entry
            val prefilledDebit = if (totalCredit > totalDebit + 0.01) formatEntry(totalCredit - totalDebit) else "0.00"
            val prefilledCredit = if (totalDebit > totalCredit + 0.01) formatEntry(totalDebit - totalCredit) else "0.00"

            OutlinedButton(
                onClick = {
                    entries.add(
                        EditEntryState(
                            id = nextEntryId(),
                            debit = prefilledDebit,
                            credit = prefilledCredit
                        )
                    )
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Legg til postering")
            }

            Spacer(Modifier.height(16.dp))

            // Chain section
            Text("Kjeding", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))

            // Auto-detected suggestions for this transaction
            if (chainSuggestions.isNotEmpty()) {
                chainSuggestions.forEach { suggestion ->
                    val isThisPrimary = suggestion.primaryTransactionId == transaction.id
                    val otherDesc = if (isThisPrimary) suggestion.secondaryDescription else suggestion.primaryDescription
                    val otherAccount = if (isThisPrimary) suggestion.secondaryAccountName else suggestion.primaryAccountName
                    val otherId = if (isThisPrimary) suggestion.secondaryTransactionId else suggestion.primaryTransactionId
                    val confidence = if (suggestion.confidence == "HIGH") "Sikker match" else "Sannsynlig match"

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    confidence,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                Text(
                                    otherDesc,
                                    style = MaterialTheme.typography.bodySmall,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Text(
                                    "$otherAccount · ${formatAmount(suggestion.amount)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                TextButton(onClick = { onChain(otherId, false) }) {
                                    Text("Kjed")
                                }
                                TextButton(onClick = { onChain(otherId, true) }) {
                                    Text("Kjed+poster")
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                }
            }

            OutlinedButton(
                onClick = { showChainPicker = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Link, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Kjed manuelt")
            }

            Spacer(Modifier.height(16.dp))

            // Save / Cancel
            if (!canSave) {
                Text(
                    text = if (!balanced) "Bilag er ikke balansert (diff: ${formatAmount(diff)})"
                    else "Velg konto for alle posteringer",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(bottom = 4.dp)
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f)
                ) { Text("Avbryt") }
                Button(
                    onClick = {
                        if (canSave) {
                            onSave(
                                UpdateTransactionRequest(
                                    transactionDate = date,
                                    description = description,
                                    reference = reference.ifBlank { null },
                                    journalEntries = entries.mapNotNull { e ->
                                        e.accountId?.let { accountId ->
                                            JournalEntryUpdate(
                                                accountId = accountId,
                                                debit = parseAmount(e.debit),
                                                credit = parseAmount(e.credit)
                                            )
                                        }
                                    }
                                )
                            )
                        }
                    },
                    enabled = canSave,
                    modifier = Modifier.weight(1f)
                ) { Text("Lagre") }
            }
        }
    }

    if (showChainPicker) {
        ChainPickerSheet(
            transactions = otherTransactions,
            onChain = { otherId, autoPost ->
                onChain(otherId, autoPost)
                showChainPicker = false
            },
            onDismiss = { showChainPicker = false }
        )
    }
}

// ─── Journal entry editor ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JournalEntryEditor(
    entry: EditEntryState,
    accounts: List<AccountResponse>,
    canRemove: Boolean,
    onUpdate: (EditEntryState) -> Unit,
    onRemove: () -> Unit
) {
    var accountSearch by remember { mutableStateOf(entry.accountNumber) }
    var dropdownExpanded by remember { mutableStateOf(false) }

    val filtered = remember(accountSearch) {
        if (accountSearch.length < 1) emptyList()
        else accounts.filter {
            it.accountNumber.startsWith(accountSearch) ||
                    it.accountName.contains(accountSearch, ignoreCase = true)
        }.take(10)
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                ExposedDropdownMenuBox(
                    expanded = dropdownExpanded && filtered.isNotEmpty(),
                    onExpandedChange = { dropdownExpanded = it },
                    modifier = Modifier.weight(1f)
                ) {
                    OutlinedTextField(
                        value = accountSearch,
                        onValueChange = { input ->
                            accountSearch = input
                            dropdownExpanded = true
                            if (accounts.none { it.accountNumber == input }) {
                                onUpdate(
                                    entry.copy(
                                        accountId = null,
                                        accountNumber = input,
                                        accountName = ""
                                    )
                                )
                            }
                        },
                        label = { Text("Konto") },
                        placeholder = { Text("Nr. eller navn") },
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth(),
                        singleLine = true,
                        supportingText = if (entry.accountName.isNotEmpty()) {
                            { Text(entry.accountName, style = MaterialTheme.typography.labelSmall) }
                        } else null,
                        trailingIcon = {
                            ExposedDropdownMenuDefaults.TrailingIcon(dropdownExpanded && filtered.isNotEmpty())
                        }
                    )
                    ExposedDropdownMenu(
                        expanded = dropdownExpanded && filtered.isNotEmpty(),
                        onDismissRequest = { dropdownExpanded = false }
                    ) {
                        filtered.forEach { account ->
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        "${account.accountNumber} ${account.accountName}",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                },
                                onClick = {
                                    accountSearch = account.accountNumber
                                    dropdownExpanded = false
                                    onUpdate(
                                        entry.copy(
                                            accountId = account.id,
                                            accountNumber = account.accountNumber,
                                            accountName = account.accountName
                                        )
                                    )
                                }
                            )
                        }
                    }
                }
                if (canRemove) {
                    Spacer(Modifier.width(4.dp))
                    IconButton(
                        onClick = onRemove,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "Fjern",
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }

            Spacer(Modifier.height(4.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = entry.debit,
                    onValueChange = { onUpdate(entry.copy(debit = it)) },
                    label = { Text("Debet") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f),
                    singleLine = true
                )
                OutlinedTextField(
                    value = entry.credit,
                    onValueChange = { onUpdate(entry.copy(credit = it)) },
                    label = { Text("Kredit") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f),
                    singleLine = true
                )
            }
        }
    }
}

// ─── Manual chain picker ───────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChainPickerSheet(
    transactions: List<TransactionResponse>,
    onChain: (Int, Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    var search by remember { mutableStateOf("") }
    var selectedId by remember { mutableStateOf<Int?>(null) }

    val filtered = remember(search, transactions) {
        if (search.isEmpty()) transactions
        else transactions.filter {
            it.description.contains(search, ignoreCase = true) ||
                    it.transactionDate.contains(search)
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp)
        ) {
            Text("Kjed med transaksjon", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = search,
                onValueChange = { search = it },
                label = { Text("Søk") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(Modifier.height(8.dp))

            LazyColumn(modifier = Modifier.heightIn(max = 320.dp)) {
                if (filtered.isEmpty()) {
                    item {
                        Text(
                            "Ingen transaksjoner",
                            modifier = Modifier.padding(16.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                items(filtered, key = { it.id }) { t ->
                    val amount = t.totalAmount()
                    val isSelected = selectedId == t.id
                    ListItem(
                        headlineContent = {
                            Text(
                                t.description,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        },
                        supportingContent = {
                            Text("${t.transactionDate} · ${formatAmount(amount)}")
                        },
                        leadingContent = if (isSelected) {
                            {
                                Icon(
                                    Icons.Default.CheckCircle,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        } else null,
                        modifier = Modifier.clickable {
                            selectedId = if (selectedId == t.id) null else t.id
                        },
                        colors = if (isSelected)
                            ListItemDefaults.colors(
                                containerColor = MaterialTheme.colorScheme.primaryContainer
                            )
                        else ListItemDefaults.colors()
                    )
                    HorizontalDivider()
                }
            }

            selectedId?.let { id ->
                Spacer(Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedButton(
                        onClick = { onChain(id, false) },
                        modifier = Modifier.weight(1f)
                    ) { Text("Kjed") }
                    Button(
                        onClick = { onChain(id, true) },
                        modifier = Modifier.weight(1f)
                    ) { Text("Kjed + poster") }
                }
            }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth()
            ) { Text("Avbryt") }
        }
    }
}
