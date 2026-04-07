package eu.privatregnskap.app.ui.attachments

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import android.app.Activity
import com.yalantis.ucrop.UCrop
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Crop
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.material3.FilterChip
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
import eu.privatregnskap.app.data.network.dto.MatchSuggestionResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.ui.common.FullScreenImageViewer
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttachmentsScreen(
    innerPadding: PaddingValues = PaddingValues(),
    initialUri: Uri? = null,
    viewModel: AttachmentsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val transactions by viewModel.transactions.collectAsStateWithLifecycle()
    val suggestedMatches by viewModel.suggestedMatches.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    var statusFilter by remember { mutableStateOf<String?>(null) }
    var searchQuery by remember { mutableStateOf("") }
    var showUploadSheet by remember { mutableStateOf(false) }
    var deletingId by remember { mutableStateOf<Int?>(null) }
    var matchingAttachmentId by remember { mutableStateOf<Int?>(null) }
    var viewingAttachment by remember { mutableStateOf<AttachmentResponse?>(null) }
    var fullScreenImageUrl by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        viewModel.message.collect { snackbarHostState.showSnackbar(it) }
    }

    LaunchedEffect(Unit) {
        viewModel.openFileEvent.collect { (uri, mimeType) ->
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, mimeType)
                flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
            }
            context.startActivity(intent)
        }
    }

    // uCrop launcher — receives crop result and uploads to server
    var cropAttachmentId by remember { mutableStateOf<Int?>(null) }
    val cropLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val croppedUri = result.data?.let { UCrop.getOutput(it) }
            val id = cropAttachmentId
            if (croppedUri != null && id != null) {
                viewModel.uploadCropped(id, croppedUri, context)
            }
        }
        cropAttachmentId = null
    }

    LaunchedEffect(Unit) {
        viewModel.cropEditEvent.collect { (attachmentId, srcUri, destUri) ->
            cropAttachmentId = attachmentId
            val options = UCrop.Options().apply {
                setFreeStyleCropEnabled(true)
                setToolbarTitle("Beskjær / roter")
                setShowCropGrid(true)
            }
            val intent = UCrop.of(srcUri, destUri)
                .withOptions(options)
                .getIntent(context)
            cropLauncher.launch(intent)
        }
    }

    // Camera launcher — needs a temp URI
    var cameraUri by remember { mutableStateOf<Uri?>(null) }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success) cameraUri?.let { showUploadSheet = true }
    }

    // Document picker (images + PDFs, uses SAF — no storage permission needed)
    var pickedUri by remember { mutableStateOf<Uri?>(null) }
    val fileLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri?.let { pickedUri = it; showUploadSheet = true }
    }

    // Handle "Open with" / share intent from outside the app
    LaunchedEffect(Unit) {
        if (initialUri != null) {
            pickedUri = initialUri
            showUploadSheet = true
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Vedlegg") },
                actions = {
                    if (!uiState.requiresSubscription) {
                        IconButton(onClick = {
                            showUploadSheet = true
                            pickedUri = null
                            cameraUri = null
                        }) {
                            Icon(Icons.Default.Add, contentDescription = "Last opp")
                        }
                    }
                    IconButton(onClick = { viewModel.loadAll(statusFilter) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Last på nytt")
                    }
                }
            )
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
                                isExtracting = uiState.extractingId == attachment.id,
                                onTap = { viewingAttachment = attachment },
                                onDelete = { deletingId = attachment.id },
                                onExtractAI = { viewModel.extractAI(attachment.id) },
                                onMatch = {
                                    matchingAttachmentId = attachment.id
                                    viewModel.loadTransactionsForMatching()
                                    viewModel.loadSuggestedMatches(attachment.id)
                                },
                                onUnmatch = { viewModel.unmatchAttachment(attachment.id) },
                                onImageTap = { fullScreenImageUrl = viewModel.imageUrl(attachment.id) },
                                onTagSearch = { tag ->
                                    searchQuery = tag
                                    viewModel.loadAll(search = tag)
                                }
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

    // Receipt detail sheet
    viewingAttachment?.let { att ->
        ReceiptDetailSheet(
            attachment = att,
            imageUrl = viewModel.imageUrl(att.id),
            isExtracting = uiState.extractingId == att.id,
            onExtractAI = { viewModel.extractAI(att.id) },
            onMatch = {
                viewingAttachment = null
                matchingAttachmentId = att.id
                viewModel.loadTransactionsForMatching()
                viewModel.loadSuggestedMatches(att.id)
            },
            onUnmatch = { viewModel.unmatchAttachment(att.id) },
            onDelete = { viewingAttachment = null; deletingId = att.id },
            onOpenExternal = { viewModel.openAttachmentExternal(att, context) },
            onCropEdit = { viewingAttachment = null; viewModel.prepareCropEdit(att, context) },
            onImageTap = { fullScreenImageUrl = viewModel.imageUrl(att.id) },
            onDismiss = { viewingAttachment = null }
        )
    }

    // Match picker sheet
    matchingAttachmentId?.let { attId ->
        MatchPickerSheet(
            transactions = transactions,
            suggestedMatches = suggestedMatches,
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
                fileLauncher.launch(arrayOf("image/*", "application/pdf"))
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

    // Full-screen image viewer
    fullScreenImageUrl?.let { url ->
        FullScreenImageViewer(imageUrl = url, onDismiss = { fullScreenImageUrl = null })
    }
}

// ─── Attachment card ──────────────────────────────────────────────────────────

@Composable
private fun AttachmentCard(
    attachment: AttachmentResponse,
    imageUrl: String,
    isExtracting: Boolean,
    onTap: () -> Unit,
    onDelete: () -> Unit,
    onExtractAI: () -> Unit,
    onImageTap: () -> Unit,
    onTagSearch: (String) -> Unit,
    onMatch: () -> Unit,
    onUnmatch: () -> Unit
) {
    val isInvoice = attachment.attachmentType == "INVOICE"

    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        onClick = onTap
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.Top
        ) {
            // Thumbnail — tappable for full-screen on images
            if (attachment.mimeType == "application/pdf") {
                Box(
                    modifier = Modifier.size(72.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.Description,
                        contentDescription = "PDF",
                        modifier = Modifier.size(40.dp),
                        tint = MaterialTheme.colorScheme.error
                    )
                }
            } else {
                AsyncImage(
                    model = imageUrl,
                    contentDescription = null,
                    modifier = Modifier
                        .size(72.dp)
                        .clickable { onImageTap() },
                    contentScale = ContentScale.Crop
                )
            }

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

                // AI tags — tappable to search
                val aiTags = listOfNotNull(
                    attachment.aiExtractedVendor,
                    attachment.aiExtractedDescription?.takeIf { it != attachment.aiExtractedVendor }
                )
                if (aiTags.isNotEmpty()) {
                    @OptIn(ExperimentalFoundationApi::class)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        aiTags.forEach { tag ->
                            FilterChip(
                                selected = false,
                                onClick = { onTagSearch(tag) },
                                label = { Text(tag, style = MaterialTheme.typography.labelSmall) },
                                modifier = Modifier.height(24.dp)
                            )
                        }
                    }
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

// ─── Receipt detail sheet ─────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ReceiptDetailSheet(
    attachment: AttachmentResponse,
    imageUrl: String,
    isExtracting: Boolean,
    onExtractAI: () -> Unit,
    onMatch: () -> Unit,
    onUnmatch: () -> Unit,
    onDelete: () -> Unit,
    onOpenExternal: () -> Unit,
    onCropEdit: () -> Unit,
    onImageTap: () -> Unit,
    onDismiss: () -> Unit
) {
    val isInvoice = attachment.attachmentType == "INVOICE"

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 32.dp)
        ) {
            // Full-width preview
            if (attachment.mimeType == "application/pdf") {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(180.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.Description,
                            contentDescription = "PDF",
                            modifier = Modifier.size(72.dp),
                            tint = MaterialTheme.colorScheme.error
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            attachment.originalFilename ?: "PDF-dokument",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            } else {
                AsyncImage(
                    model = imageUrl,
                    contentDescription = "Vedlegg",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(300.dp)
                        .clickable { onImageTap() },
                    contentScale = ContentScale.Fit
                )
            }

            Column(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Title row
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        attachment.originalFilename ?: if (isInvoice) "Faktura" else "Kvittering",
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.weight(1f)
                    )
                    TypeBadge(isInvoice)
                }

                HorizontalDivider()

                // Metadata rows
                @Composable
                fun DetailRow(label: String, value: String) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(label, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(value, style = MaterialTheme.typography.bodySmall)
                    }
                }

                val vendor = attachment.aiExtractedVendor
                if (vendor != null) DetailRow("Leverandør", vendor)

                val date = attachment.receiptDate ?: attachment.aiExtractedDate
                if (date != null) DetailRow("Dato", date)

                if (isInvoice && attachment.dueDate != null)
                    DetailRow("Forfallsdato", attachment.dueDate)

                val amount = attachment.amount ?: attachment.aiExtractedAmount
                if (amount != null)
                    DetailRow("Beløp", String.format(java.util.Locale.US, "%.2f kr", amount))

                if (attachment.description != null)
                    DetailRow("Beskrivelse", attachment.description)

                if (attachment.aiSuggestedAccount != null)
                    DetailRow("Foreslått konto", attachment.aiSuggestedAccount)

                val conf = attachment.aiConfidence
                if (conf != null)
                    DetailRow("AI-sikkerhet", "${(conf * 100).toInt()}%")

                if (attachment.status == "MATCHED" && attachment.matchedTransactionId != null)
                    DetailRow("Matchet til", "Transaksjon #${attachment.matchedTransactionId}")

                HorizontalDivider()

                // Action buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (attachment.aiExtractedVendor == null) {
                        OutlinedButton(
                            onClick = onExtractAI,
                            enabled = !isExtracting,
                            modifier = Modifier.weight(1f)
                        ) {
                            if (isExtracting) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            } else {
                                Text("AI-gjenkjenning")
                            }
                        }
                    }
                    if (attachment.status == "MATCHED") {
                        OutlinedButton(onClick = onUnmatch, modifier = Modifier.weight(1f)) {
                            Icon(Icons.Default.LinkOff, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Fjern kobling")
                        }
                    } else {
                        OutlinedButton(onClick = onMatch, modifier = Modifier.weight(1f)) {
                            Icon(Icons.Default.Link, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Koble til transaksjon")
                        }
                    }
                }

                if (attachment.mimeType != "application/pdf") {
                    OutlinedButton(
                        onClick = onCropEdit,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Crop, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Beskjær / roter")
                    }
                }

                if (attachment.mimeType == "application/pdf") {
                    OutlinedButton(
                        onClick = onOpenExternal,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Åpne PDF i ekstern app")
                    }
                }

                Button(
                    onClick = onDelete,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                        contentColor = MaterialTheme.colorScheme.onErrorContainer
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Slett vedlegg")
                }
            }
        }
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
    suggestedMatches: List<MatchSuggestionResponse>,
    onMatch: (Int) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    val filtered = if (query.isBlank()) transactions else transactions.filter { tx ->
        tx.description.contains(query, ignoreCase = true) ||
        tx.transactionDate.contains(query)
    }
    // IDs already shown in suggestions — don't duplicate in the full list
    val suggestedIds = suggestedMatches.map { it.transaction.id }.toSet()

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

            LazyColumn(modifier = Modifier.fillMaxWidth()) {
                // Suggestions section
                if (suggestedMatches.isNotEmpty() && query.isBlank()) {
                    item {
                        Text(
                            "Foreslåtte treff",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(vertical = 4.dp)
                        )
                    }
                    items(suggestedMatches, key = { "sug_${it.transaction.id}" }) { suggestion ->
                        val tx = suggestion.transaction
                        val debit = tx.journalEntries.firstOrNull()?.debit
                        val credit = tx.journalEntries.firstOrNull()?.credit
                        val amountVal = debit ?: credit
                        val amountStr = if (amountVal != null)
                            String.format(java.util.Locale.US, "  %.2f kr", amountVal) else ""
                        ListItem(
                            headlineContent = {
                                Text(tx.description, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                            supportingContent = {
                                Column {
                                    Text("${tx.transactionDate}$amountStr",
                                        style = MaterialTheme.typography.bodySmall)
                                    if (suggestion.reasons.isNotEmpty()) {
                                        Text(
                                            suggestion.reasons.joinToString(" · "),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                }
                            },
                            trailingContent = {
                                IconButton(onClick = { onMatch(tx.id) }) {
                                    Icon(Icons.Default.Link, contentDescription = "Koble")
                                }
                            }
                        )
                        HorizontalDivider()
                    }
                    item {
                        Text(
                            "Alle transaksjoner",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 12.dp, bottom = 4.dp)
                        )
                    }
                }

                // Full list (excluding already-suggested items when not searching)
                val listItems = if (query.isBlank()) filtered.filter { it.id !in suggestedIds } else filtered
                if (listItems.isEmpty() && suggestedMatches.isEmpty()) {
                    item {
                        Box(
                            Modifier.fillMaxWidth().height(120.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Ingen transaksjoner funnet",
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                } else {
                    items(listItems, key = { it.id }) { tx ->
                        val debit = tx.journalEntries.firstOrNull()?.debit
                        val credit = tx.journalEntries.firstOrNull()?.credit
                        val amountVal = debit ?: credit
                        val amountStr = if (amountVal != null)
                            String.format(java.util.Locale.US, "  %.2f kr", amountVal) else ""
                        ListItem(
                            headlineContent = {
                                Text(tx.description, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            },
                            supportingContent = {
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
