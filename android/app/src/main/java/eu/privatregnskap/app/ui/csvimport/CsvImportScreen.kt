package eu.privatregnskap.app.ui.csvimport

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CsvImportScreen(
    innerPadding: PaddingValues,
    onBack: () -> Unit,
    onImported: () -> Unit,
    viewModel: CsvImportViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    val pickFile = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            val name = uri.lastPathSegment?.substringAfterLast('/') ?: "import.csv"
            val bytes = runCatching {
                context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            }.getOrNull()
            if (bytes != null) viewModel.setFile(name, bytes)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Importer CSV") },
                navigationIcon = {
                    IconButton(onClick = {
                        if (state.step == CsvImportStep.MAP_COLUMNS) viewModel.back() else onBack()
                    }) {
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
            when (state.step) {
                CsvImportStep.PICK_FILE -> PickFileStep(
                    state = state,
                    viewModel = viewModel,
                    onPickFile = { pickFile.launch(arrayOf("text/csv", "text/comma-separated-values", "text/plain", "*/*")) }
                )
                CsvImportStep.MAP_COLUMNS -> MapColumnsStep(state, viewModel)
                CsvImportStep.DONE -> DoneStep(state, onImported)
            }

            if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
        }
    }
}

@Composable
private fun PickFileStep(
    state: CsvImportUiState,
    viewModel: CsvImportViewModel,
    onPickFile: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        item {
            Text(
                text = "Importer transaksjoner fra en CSV-fil lastet ned fra nettbanken. " +
                    "De havner i posteringskøen, der du fører dem videre.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp)
            )
        }

        item { SectionTitle("Bankkonto") }
        if (state.bankAccounts.isEmpty()) {
            item {
                Text(
                    text = "Dette regnskapet har ingen bankkontoer ennå. Opprett en først " +
                        "— transaksjonene må importeres til en konto.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp)
                )
            }
        }
        item {
            Row(
                modifier = Modifier
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                state.bankAccounts.forEach { account ->
                    FilterChip(
                        selected = state.selectedBankAccountId == account.id,
                        onClick = { viewModel.setBankAccount(account.id) },
                        label = { Text(account.name, maxLines = 1) }
                    )
                }
            }
        }

        item {
            SectionTitle("Fil")
            Row(
                modifier = Modifier.padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedButton(onClick = onPickFile) { Text("Velg fil") }
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = state.fileName ?: "Ingen fil valgt",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        item {
            SectionTitle("Skilletegn")
            ChipRow(
                options = CSV_DELIMITERS,
                selected = state.delimiter,
                onSelect = { viewModel.setDelimiter(it) }
            )
        }

        item {
            state.error?.let { ErrorText(it) }
            Button(
                onClick = { viewModel.loadPreview() },
                enabled = state.canPreview,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) { Text("Les fil") }
        }
    }
}

@Composable
private fun MapColumnsStep(state: CsvImportUiState, viewModel: CsvImportViewModel) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        item {
            Text(
                text = "Fant ${state.totalRows} rader. Velg hvilke kolonner som er hva.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp)
            )
        }

        if (state.savedMappings.isNotEmpty()) {
            item {
                SectionTitle("Lagrede oppsett")
                Row(
                    modifier = Modifier
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    state.savedMappings.forEach { mapping ->
                        AssistChip(
                            onClick = { viewModel.applySavedMapping(mapping) },
                            label = { Text(mapping.name) }
                        )
                    }
                }
            }
        }

        item {
            PreviewTable(state)
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        }

        item {
            ColumnPicker("Dato *", state.columns, state.dateColumn) { viewModel.setDateColumn(it) }
            ColumnPicker("Beskrivelse *", state.columns, state.descriptionColumn) { viewModel.setDescriptionColumn(it) }
            ColumnPicker("Beløp *", state.columns, state.amountColumn) { viewModel.setAmountColumn(it) }
            ColumnPicker("Referanse", state.columns, state.referenceColumn, allowNone = true) {
                viewModel.setReferenceColumn(it)
            }
        }

        item {
            SectionTitle("Datoformat")
            ChipRow(
                options = CSV_DATE_FORMATS.map { it to it },
                selected = state.dateFormat,
                onSelect = { viewModel.setDateFormat(it) }
            )
            SectionTitle("Desimalskilletegn")
            ChipRow(
                options = CSV_DECIMAL_SEPARATORS,
                selected = state.decimalSeparator,
                onSelect = { viewModel.setDecimalSeparator(it) }
            )
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Snu fortegn")
                    Text(
                        "Hvis uttak står som positive tall i filen",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(
                    checked = state.invertAmount,
                    onCheckedChange = { viewModel.setInvertAmount(it) }
                )
            }
        }

        item {
            state.error?.let { ErrorText(it) }
            Button(
                onClick = { viewModel.import() },
                enabled = state.canImport,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) { Text("Importer ${state.totalRows} rader") }
        }
    }
}

@Composable
private fun DoneStep(state: CsvImportUiState, onImported: () -> Unit) {
    val result = state.result
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "${result?.imported ?: 0} transaksjoner importert",
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center
        )
        if ((result?.failed ?: 0) > 0) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "${result?.failed} rader ble hoppet over",
                color = MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center
            )
            result?.errors?.take(5)?.forEach { error ->
                Text(
                    text = error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center
                )
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Transaksjonene ligger nå i posteringskøen.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onImported) { Text("Til posteringskøen") }
    }
}

@Composable
private fun PreviewTable(state: CsvImportUiState) {
    Card(modifier = Modifier.padding(horizontal = 16.dp)) {
        Column(
            modifier = Modifier
                .horizontalScroll(rememberScrollState())
                .padding(8.dp)
        ) {
            Row {
                state.columns.forEach { column ->
                    Text(
                        text = column,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.width(110.dp).padding(2.dp),
                        maxLines = 1
                    )
                }
            }
            state.previewRows.take(3).forEach { row ->
                Row {
                    row.forEach { cell ->
                        Text(
                            text = cell,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.width(110.dp).padding(2.dp),
                            maxLines = 1
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ColumnPicker(
    label: String,
    columns: List<String>,
    selected: String?,
    allowNone: Boolean = false,
    onSelect: (String?) -> Unit
) {
    SectionTitle(label)
    Row(
        modifier = Modifier
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (allowNone) {
            FilterChip(
                selected = selected == null,
                onClick = { onSelect(null) },
                label = { Text("Ingen") }
            )
        }
        columns.forEach { column ->
            FilterChip(
                selected = selected == column,
                onClick = { onSelect(column) },
                label = { Text(column, maxLines = 1) }
            )
        }
    }
}

@Composable
private fun ChipRow(
    options: List<Pair<String, String>>,
    selected: String,
    onSelect: (String) -> Unit
) {
    Row(
        modifier = Modifier
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        options.forEach { (value, label) ->
            FilterChip(
                selected = selected == value,
                onClick = { onSelect(value) },
                label = { Text(label) }
            )
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

@Composable
private fun ErrorText(message: String) {
    Text(
        text = message,
        color = MaterialTheme.colorScheme.error,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
    )
}
