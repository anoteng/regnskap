package eu.privatregnskap.app.ui.attachments

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttachmentsScreen(
    innerPadding: PaddingValues = PaddingValues(),
    viewModel: AttachmentsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val transactions by viewModel.transactions.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    var statusFilter by remember { mutableStateOf<String?>(null) }
    var searchQuery by remember { mutableStateOf("") }
    var showUploadSheet by remember { mutableStateOf(false) }
    var deletingId by remember { mutableStateOf<Int?>(null) }
    var matchingAttachmentId by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(Unit) {
        viewModel.message.collect { snackbarHostState.showSnackbar(it) }
    }

    // Camera launcher — needs a temp URI
    var cameraUri by remember { mutableStateOf<Uri?>(null) }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success) cameraUri?.let { showUploadSheet = true }
    }

    // File picker launcher
    var pickedUri by remember { mutableStateOf<Uri?>(null) }
    val fileLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let { pickedUri = it; showUploadSheet = true }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Vedlegg") },
                actions = {
                    IconButton(onClick = { viewModel.loadAll(statusFilter) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Last på nytt")
                    }
                }
            )
        },
        floatingActionButton = {
            if (!uiState.requiresSubscription) {
                FloatingActionButton(onClick = {
                    // Show picker choice via bottom sheet instead of directly launching
                    showUploadSheet = true
                    pickedUri = null
                    cameraUri = null
                }) {
                    Icon(Icons.Default.Add, contentDescription = "Last opp")
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { scaffoldPadding ->

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(scaffoldPadding)
                .padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            if (!uiState.requiresSubscription) {
                // Search bar
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it; viewModel.loadAll(statusFilter, it) },
                    placeholder = { Text("Søk leverandør, filnavn, beskrivelse…") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    trailingIcon = {
                        if (searchQuery.isNotEmpty()) {
                            IconButton(onClick = { searchQuery = ""; viewModel.loadAll(statusFilter, null) }) {
                                Icon(Icons.Default.Clear, contentDescription = "Tøm søk")
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 4.dp),
                    singleLine = true
                )

                // Filter chips
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    FilterChip(
                        selected = statusFilter == null,
                        onClick = { statusFilter = null; viewModel.loadAll(null, searchQuery.ifBlank { null }) },
                        label = { Text("Alle") }
                    )
                    FilterChip(
                        selected = statusFilter == "PENDING",
                        onClick = { statusFilter = "PENDING"; viewModel.loadAll("PENDING", searchQuery.ifBlank { null }) },
                        label = { Text("Ubehandlede") }
                    )
                    FilterChip(
                        selected = statusFilter == "MATCHED",
                        onClick = { statusFilter = "MATCHED"; viewModel.loadAll("MATCHED", searchQuery.ifBlank { null }) },
                        label = { Text("Matchede") }
                    )
                }
            }

            when {
                uiState.isLoading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }

                uiState.requiresSubscription -> {
                    SubscriptionRequiredMessage()
                }

                uiState.error != null -> {
                    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                        Text(uiState.error!!, color = MaterialTheme.colorScheme.error)
                    }
                }

                uiState.attachments.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Ingen vedlegg", style = MaterialTheme.typography.bodyLarge)
                            Spacer(Modifier.height(8.dp))
                            Text(
                                "Trykk + for å laste opp kvittering eller faktura",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }

                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(uiState.attachments, key = { it.id }) { attachment ->
                            AttachmentCard(
                                attachment = attachment,
                                imageUrl = viewModel.imageUrl(attachment.id),
                                isExtracting = uiState.isExtracting,
                                onDelete = { deletingId = attachment.id },
                                onExtractAI = { viewModel.extractAI(attachment.id) },
                                onMatch = {
                                    matchingAttachmentId = attachment.id
                                    viewModel.loadTransactionsForMatching()
                                },
                                onUnmatch = { viewModel.unmatchAttachment(attachment.id) }
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
            title = { Text("Slett vedlegg") },
            text = { Text("Er du sikker? Dette kan ikke angres.") },
            confirmButton = {
                TextButton(onClick = { viewModel.delete(id); deletingId = null }) {
                    Text("Slett", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { deletingId = null }) { Text("Avbryt") }
            }
        )
    }

    // Match picker sheet
    matchingAttachmentId?.let { attId ->
        MatchPickerSheet(
            transactions = transactions,
            onMatch = { txId -> viewModel.matchAttachment(attId, txId); matchingAttachmentId = null },
            onDismiss = { matchingAttachmentId = null }
        )
    }

    // Upload / source picker sheet
    if (showUploadSheet && cameraUri == null && pickedUri == null) {
        SourcePickerSheet(
            onCamera = {
                val tmpFile = File.createTempFile("attachment_", ".jpg", context.cacheDir)
                val uri = FileProvider.getUriForFile(
                    context, "${context.packageName}.fileprovider", tmpFile
                )
                cameraUri = uri
                showUploadSheet = false
                cameraLauncher.launch(uri)
            },
            onFile = {
                showUploadSheet = false
                fileLauncher.launch("image/*")
            },
            onDismiss = { showUploadSheet = false }
        )
    }

    // Upload metadata sheet — shown after source is picked
    val activeUri = pickedUri ?: cameraUri
    if (showUploadSheet && activeUri != null) {
        UploadMetadataSheet(
            uri = activeUri,
            onUpload = { type, date, dueDate, amount, desc ->
                viewModel.upload(context, activeUri, type, date, dueDate, amount, desc)
                pickedUri = null
                cameraUri = null
                showUploadSheet = false
            },
            onDismiss = {
                pickedUri = null
                cameraUri = null
                showUploadSheet = false
            }
        )
    }
}

// ─── Attachment card ──────────────────────────────────────────────────────────

@Composable
private fun AttachmentCard(
    attachment: AttachmentResponse,
    imageUrl: String,
    isExtracting: Boolean,
    onDelete: () -> Unit,
    onExtractAI: () -> Unit,
    onMatch: () -> Unit,
    onUnmatch: () -> Unit
) {
    val isInvoice = attachment.attachmentType == "INVOICE"

    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.Top
        ) {
            // Thumbnail
            AsyncImage(
                model = imageUrl,
                contentDescription = null,
                modifier = Modifier.size(72.dp),
                contentScale = ContentScale.Crop
            )

            Spacer(Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                // Header row: filename + type badge
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text(
                        text = attachment.originalFilename ?: if (isInvoice) "Faktura" else "Kvittering",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                    TypeBadge(isInvoice)
                }

                Spacer(Modifier.height(2.dp))

                // Vendor from AI
                val vendor = attachment.aiExtractedVendor
                if (vendor != null) {
                    Text(vendor, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary)
                }

                // Date
                val date = attachment.receiptDate ?: attachment.aiExtractedDate
                if (date != null) {
                    Text("Dato: $date", style = MaterialTheme.typography.bodySmall)
                }

                // Due date for invoices
                if (isInvoice && attachment.dueDate != null) {
                    Text(
                        "Forfall: ${attachment.dueDate}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                // Amount
                val amount = attachment.amount ?: attachment.aiExtractedAmount
                if (amount != null) {
                    Text(
                        String.format(java.util.Locale.US, "%.2f kr", amount),
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                // Matched status
                if (attachment.status == "MATCHED") {
                    Text(
                        "Matchet til transaksjon #${attachment.matchedTransactionId}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                Spacer(Modifier.height(6.dp))

                // Actions
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (attachment.aiExtractedVendor == null) {
                        OutlinedButton(
                            onClick = onExtractAI,
                            enabled = !isExtracting,
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            if (isExtracting) {
                                CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                            } else {
                                Text("AI", style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                    if (attachment.status == "MATCHED") {
                        IconButton(onClick = onUnmatch, modifier = Modifier.size(32.dp)) {
                            Icon(
                                Icons.Default.LinkOff,
                                contentDescription = "Fjern kobling",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    } else {
                        IconButton(onClick = onMatch, modifier = Modifier.size(32.dp)) {
                            Icon(
                                Icons.Default.Link,
                                contentDescription = "Koble til transaksjon",
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                    IconButton(onClick = onDelete, modifier = Modifier.size(32.dp)) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = "Slett",
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TypeBadge(isInvoice: Boolean) {
    val (label, color) = if (isInvoice)
        "Faktura" to MaterialTheme.colorScheme.primaryContainer
    else
        "Kvittering" to MaterialTheme.colorScheme.secondaryContainer

    Surface(shape = MaterialTheme.shapes.extraSmall, color = color) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

// ─── Source picker sheet ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SourcePickerSheet(
    onCamera: () -> Unit,
    onFile: () -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp)
                .padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("Last opp vedlegg", style = MaterialTheme.typography.titleLarge)

            Button(onClick = onCamera, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.CameraAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Ta bilde")
            }
            OutlinedButton(onClick = onFile, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Folder, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Velg fil")
            }
        }
    }
}

// ─── Upload metadata sheet ────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun UploadMetadataSheet(
    uri: Uri,
    onUpload: (type: String, date: String?, dueDate: String?, amount: String?, desc: String?) -> Unit,
    onDismiss: () -> Unit
) {
    var attachmentType by remember { mutableStateOf("RECEIPT") }
    var receiptDate by remember { mutableStateOf("") }
    var dueDate by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("Vedleggsdetaljer", style = MaterialTheme.typography.titleLarge)

            // Type selector
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = attachmentType == "RECEIPT",
                    onClick = { attachmentType = "RECEIPT" },
                    label = { Text("Kvittering") }
                )
                FilterChip(
                    selected = attachmentType == "INVOICE",
                    onClick = { attachmentType = "INVOICE" },
                    label = { Text("Faktura") }
                )
            }

            OutlinedTextField(
                value = receiptDate,
                onValueChange = { receiptDate = it },
                label = { Text(if (attachmentType == "INVOICE") "Fakturadato" else "Dato") },
                placeholder = { Text("ÅÅÅÅ-MM-DD") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            if (attachmentType == "INVOICE") {
                OutlinedTextField(
                    value = dueDate,
                    onValueChange = { dueDate = it },
                    label = { Text("Forfallsdato") },
                    placeholder = { Text("ÅÅÅÅ-MM-DD") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it },
                label = { Text("Beløp (valgfritt)") },
                placeholder = { Text("0.00") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            OutlinedTextField(
                value = description,
                onValueChange = { description = it },
                label = { Text("Beskrivelse (valgfritt)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Avbryt")
                }
                Button(
                    onClick = {
                        onUpload(
                            attachmentType,
                            receiptDate.ifBlank { null },
                            dueDate.ifBlank { null },
                            amount.ifBlank { null },
                            description.ifBlank { null }
                        )
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Last opp")
                }
            }
        }
    }
}

// ─── Match picker sheet ───────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MatchPickerSheet(
    transactions: List<TransactionResponse>,
    onMatch: (Int) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    val filtered = if (query.isBlank()) transactions else transactions.filter { tx ->
        tx.description.contains(query, ignoreCase = true) ||
        tx.transactionDate.contains(query)
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
            Text("Velg transaksjon", style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(bottom = 8.dp))

            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("Søk…") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                trailingIcon = {
                    if (query.isNotEmpty()) {
                        IconButton(onClick = { query = "" }) {
                            Icon(Icons.Default.Clear, contentDescription = "Tøm")
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Spacer(Modifier.height(8.dp))

            if (filtered.isEmpty()) {
                Box(
                    Modifier.fillMaxWidth().height(120.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Ingen transaksjoner funnet",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                LazyColumn(modifier = Modifier.fillMaxWidth()) {
                    items(filtered, key = { it.id }) { tx ->
                        ListItem(
                            headlineContent = {
                                Text(tx.description ?: "Ingen beskrivelse",
                                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                            supportingContent = {
                                val debit = tx.journalEntries.firstOrNull()?.debit
                                val credit = tx.journalEntries.firstOrNull()?.credit
                                val amountVal = debit ?: credit
                                val amountStr = if (amountVal != null)
                                    String.format(java.util.Locale.US, "  %.2f kr", amountVal) else ""
                                Text("${tx.transactionDate}$amountStr",
                                    style = MaterialTheme.typography.bodySmall)
                            },
                            trailingContent = {
                                IconButton(onClick = { onMatch(tx.id) }) {
                                    Icon(Icons.Default.Link, contentDescription = "Koble")
                                }
                            }
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

// ─── Subscription required ────────────────────────────────────────────────────

@Composable
private fun SubscriptionRequiredMessage() {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Vedlegg krever abonnement",
                style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Text(
                "Basic: kvitteringer og fakturaer\nPremium: + AI-gjenkjenning av beløp og dato",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
