package eu.privatregnskap.app.ui.common

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * Ledger switcher. Every screen reads its data from the selected ledger, so
 * picking one here reloads the whole app.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LedgerPickerSheet(
    onDismiss: () -> Unit,
    viewModel: LedgerPickerViewModel = hiltViewModel()
) {
    val ledgers by viewModel.ledgers.collectAsStateWithLifecycle()
    val selectedId by viewModel.selectedLedgerId.collectAsStateWithLifecycle()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Velg regnskap",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            )
            LazyColumn(modifier = Modifier.fillMaxWidth()) {
                items(ledgers, key = { it.id }) { ledger ->
                    val isSelected = ledger.id == selectedId
                    ListItem(
                        headlineContent = {
                            Text(
                                text = ledger.name,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                            )
                        },
                        supportingContent = { Text(roleLabel(ledger.userRole)) },
                        trailingContent = {
                            if (isSelected) {
                                Icon(Icons.Default.Check, contentDescription = "Valgt")
                            }
                        },
                        modifier = Modifier.clickable {
                            viewModel.select(ledger.id)
                            onDismiss()
                        }
                    )
                }
            }
        }
    }
}

private fun roleLabel(role: String): String = when (role) {
    "OWNER" -> "Eier"
    "MEMBER" -> "Medlem"
    "VIEWER" -> "Leser"
    else -> role
}
