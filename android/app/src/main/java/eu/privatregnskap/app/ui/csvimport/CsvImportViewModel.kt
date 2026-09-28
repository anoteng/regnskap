package eu.privatregnskap.app.ui.csvimport

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.BankAccountResponse
import eu.privatregnskap.app.data.network.dto.CsvImportResultResponse
import eu.privatregnskap.app.data.network.dto.CsvMappingResponse
import eu.privatregnskap.app.data.repository.CsvImportRepository
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONObject
import javax.inject.Inject

enum class CsvImportStep { PICK_FILE, MAP_COLUMNS, DONE }

val CSV_DELIMITERS = listOf("," to "Komma", ";" to "Semikolon", "\t" to "Tabulator")
val CSV_DATE_FORMATS = listOf("DD.MM.YYYY", "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY")
val CSV_DECIMAL_SEPARATORS = listOf("," to "Komma (1 234,56)", "." to "Punktum (1,234.56)")

data class CsvImportUiState(
    val step: CsvImportStep = CsvImportStep.PICK_FILE,
    val isLoading: Boolean = false,
    val error: String? = null,

    val bankAccounts: List<BankAccountResponse> = emptyList(),
    val selectedBankAccountId: Int? = null,
    val savedMappings: List<CsvMappingResponse> = emptyList(),

    val fileName: String? = null,
    val delimiter: String = ";",

    val columns: List<String> = emptyList(),
    val previewRows: List<List<String>> = emptyList(),
    val totalRows: Int = 0,

    val dateColumn: String? = null,
    val descriptionColumn: String? = null,
    val amountColumn: String? = null,
    val referenceColumn: String? = null,
    val dateFormat: String = "DD.MM.YYYY",
    val decimalSeparator: String = ",",
    val invertAmount: Boolean = false,
    val skipRows: Int = 0,

    val result: CsvImportResultResponse? = null
) {
    val fileChosen: Boolean get() = fileName != null

    val canPreview: Boolean
        get() = fileChosen && selectedBankAccountId != null && !isLoading

    val canImport: Boolean
        get() = !isLoading && selectedBankAccountId != null &&
            !dateColumn.isNullOrBlank() && !descriptionColumn.isNullOrBlank() &&
            !amountColumn.isNullOrBlank()
}

@HiltViewModel
class CsvImportViewModel @Inject constructor(
    private val repository: CsvImportRepository,
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(CsvImportUiState())
    val uiState: StateFlow<CsvImportUiState> = _uiState.asStateFlow()

    /** Kept out of state: the file can be large and never needs to be rendered. */
    private var fileBytes: ByteArray? = null
    private var ledgerId: Int? = null

    init {
        viewModelScope.launch {
            ledgerSelection.ensureLoaded()
            ledgerId = ledgerSelection.selected.value
            loadAccountsAndMappings()
        }
    }

    private suspend fun loadAccountsAndMappings() {
        _uiState.update { it.copy(isLoading = true, error = null) }
        val accounts = repository.getBankAccounts(ledgerId).getOrElse { e ->
            _uiState.update {
                it.copy(isLoading = false, error = e.message ?: "Kunne ikke hente bankkontoer")
            }
            return
        }
        val mappings = repository.getMappings(ledgerId).getOrDefault(emptyList())
        _uiState.update {
            it.copy(
                isLoading = false,
                bankAccounts = accounts,
                selectedBankAccountId = it.selectedBankAccountId ?: accounts.firstOrNull()?.id,
                savedMappings = mappings
            )
        }
    }

    fun setBankAccount(id: Int) = _uiState.update { it.copy(selectedBankAccountId = id) }

    fun setDelimiter(value: String) = _uiState.update { it.copy(delimiter = value) }

    fun setFile(name: String, bytes: ByteArray) {
        fileBytes = bytes
        _uiState.update { it.copy(fileName = name, error = null) }
    }

    fun loadPreview() {
        val state = _uiState.value
        val bytes = fileBytes ?: return
        val name = state.fileName ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.preview(name, bytes, state.delimiter).fold(
                onSuccess = { preview ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            step = CsvImportStep.MAP_COLUMNS,
                            columns = preview.columns,
                            previewRows = preview.preview,
                            totalRows = preview.totalRows,
                            // Guess the obvious columns so most files need no fiddling
                            dateColumn = it.dateColumn ?: guess(preview.columns, "dato", "date", "bokf"),
                            descriptionColumn = it.descriptionColumn
                                ?: guess(preview.columns, "tekst", "beskriv", "description", "melding"),
                            amountColumn = it.amountColumn
                                ?: guess(preview.columns, "beløp", "belop", "amount", "sum")
                        )
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isLoading = false, error = e.message ?: "Kunne ikke lese filen")
                    }
                }
            )
        }
    }

    fun applySavedMapping(mapping: CsvMappingResponse) = _uiState.update {
        it.copy(
            dateColumn = mapping.dateColumn,
            descriptionColumn = mapping.descriptionColumn,
            amountColumn = mapping.amountColumn,
            referenceColumn = mapping.referenceColumn,
            dateFormat = mapping.dateFormat,
            decimalSeparator = mapping.decimalSeparator,
            delimiter = mapping.delimiter,
            invertAmount = mapping.invertAmount,
            skipRows = mapping.skipRows
        )
    }

    fun setDateColumn(value: String?) = _uiState.update { it.copy(dateColumn = value) }
    fun setDescriptionColumn(value: String?) = _uiState.update { it.copy(descriptionColumn = value) }
    fun setAmountColumn(value: String?) = _uiState.update { it.copy(amountColumn = value) }
    fun setReferenceColumn(value: String?) = _uiState.update { it.copy(referenceColumn = value) }
    fun setDateFormat(value: String) = _uiState.update { it.copy(dateFormat = value) }
    fun setDecimalSeparator(value: String) = _uiState.update { it.copy(decimalSeparator = value) }
    fun setInvertAmount(value: Boolean) = _uiState.update { it.copy(invertAmount = value) }
    fun setSkipRows(value: Int) = _uiState.update { it.copy(skipRows = value.coerceAtLeast(0)) }

    fun back() = _uiState.update { it.copy(step = CsvImportStep.PICK_FILE, error = null) }

    fun import() {
        val state = _uiState.value
        val bytes = fileBytes ?: return
        val name = state.fileName ?: return
        val accountId = state.selectedBankAccountId ?: return
        if (!state.canImport) return

        val config = JSONObject().apply {
            put("date_column", state.dateColumn)
            put("description_column", state.descriptionColumn)
            put("amount_column", state.amountColumn)
            state.referenceColumn?.takeIf { it.isNotBlank() }?.let { put("reference_column", it) }
            put("date_format", state.dateFormat)
            put("decimal_separator", state.decimalSeparator)
            put("delimiter", state.delimiter)
            put("invert_amount", state.invertAmount)
            put("skip_rows", state.skipRows)
        }.toString()

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.import(ledgerId, accountId, name, bytes, config).fold(
                onSuccess = { result ->
                    _uiState.update {
                        it.copy(isLoading = false, step = CsvImportStep.DONE, result = result)
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isLoading = false, error = e.message ?: "Importen feilet")
                    }
                }
            )
        }
    }

    private fun guess(columns: List<String>, vararg needles: String): String? =
        columns.firstOrNull { column ->
            needles.any { column.contains(it, ignoreCase = true) }
        }
}
