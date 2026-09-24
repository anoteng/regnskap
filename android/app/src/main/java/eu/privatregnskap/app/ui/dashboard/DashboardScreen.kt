package eu.privatregnskap.app.ui.dashboard

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.ui.settlement.MemberCard
import eu.privatregnskap.app.ui.settlement.formatKr
import eu.privatregnskap.app.ui.settlement.monthLabel
import java.time.YearMonth
import eu.privatregnskap.app.ui.auth.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    innerPadding: PaddingValues = PaddingValues(),
    onOpenSettlement: () -> Unit = {},
    viewModel: DashboardViewModel = hiltViewModel()
) {
    val transactionsState by viewModel.transactionsState.collectAsStateWithLifecycle()
    val settlementState by viewModel.settlementState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Hjem") },
                actions = {
                    IconButton(onClick = { viewModel.loadTransactions() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Last på nytt")
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
            when (val state = transactionsState) {
                is UiState.Loading, UiState.Idle -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                is UiState.Error -> {
                    Text(
                        text = state.message,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(24.dp)
                    )
                }
                is UiState.Success -> {
                    val transactions = state.data
                    LazyColumn(modifier = Modifier.fillMaxSize()) {
                        when (val settlement = settlementState) {
                            is UiState.Success -> settlement.data?.let { calc ->
                                item(key = "settlement") {
                                    SettlementSummaryCard(calc, onClick = onOpenSettlement)
                                }
                            }
                            is UiState.Error -> item(key = "settlement-error") {
                                Text(
                                    text = "Kunne ikke hente månedsavregning: ${settlement.message}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error,
                                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                                )
                            }
                            else -> Unit
                        }
                        item(key = "tx-header") {
                            Text(
                                text = "Siste transaksjoner",
                                style = MaterialTheme.typography.titleSmall,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 4.dp)
                            )
                        }
                        if (transactions.isEmpty()) {
                            item(key = "tx-empty") {
                                Text(
                                    text = "Ingen transaksjoner",
                                    textAlign = TextAlign.Center,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(24.dp)
                                )
                            }
                        } else {
                            items(transactions) { transaction ->
                                TransactionItem(transaction)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SettlementSummaryCard(calc: SettlementCalculationResponse, onClick: () -> Unit) {
    Column(modifier = Modifier.padding(top = 8.dp)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Månedsavregning · ${monthLabel(YearMonth.parse(calc.month))}",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    text = "Prognose ${formatKr(calc.totals.forecastTotal)} · bokført ${formatKr(calc.totals.booked)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = "Vis detaljer",
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        calc.members.forEach { member ->
            Box(modifier = Modifier.clickable(onClick = onClick)) {
                MemberCard(member, compact = true)
            }
        }
    }
}

@Composable
private fun TransactionItem(transaction: TransactionResponse) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = transaction.description,
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = transaction.transactionDate,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = transaction.status,
                style = MaterialTheme.typography.labelSmall,
                color = when (transaction.status) {
                    "POSTED" -> MaterialTheme.colorScheme.primary
                    "DRAFT" -> MaterialTheme.colorScheme.onSurfaceVariant
                    else -> MaterialTheme.colorScheme.onSurface
                }
            )
        }
    }
}
