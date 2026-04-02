package eu.privatregnskap.app.ui.budget

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.BudgetReportLine
import eu.privatregnskap.app.data.network.dto.BudgetResponse
import java.time.LocalDate

private val MONTH_NAMES = listOf(
    "Jan", "Feb", "Mar", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Des"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BudgetScreen(innerPadding: PaddingValues) {
    val viewModel: BudgetViewModel = hiltViewModel()
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val reportState by viewModel.reportState.collectAsStateWithLifecycle()

    var selectedBudget by rememberSaveable { mutableStateOf<BudgetResponse?>(null) }
    // null = year total, 1-12 = specific month
    var selectedMonth by rememberSaveable { mutableStateOf<Int?>(LocalDate.now().monthValue) }

    BackHandler(enabled = selectedBudget != null) {
        selectedBudget = null
        viewModel.clearReport()
    }

    if (selectedBudget == null) {
        // ── Budget list ──────────────────────────────────────────────────────
        Scaffold(
            topBar = { TopAppBar(title = { Text("Budsjett") }) }
        ) { scaffoldPadding ->
            val combinedPadding = PaddingValues(
                top = scaffoldPadding.calculateTopPadding(),
                bottom = innerPadding.calculateBottomPadding()
            )
            when {
                uiState.isLoading -> Box(
                    Modifier.fillMaxSize().padding(combinedPadding),
                    contentAlignment = Alignment.Center
                ) { CircularProgressIndicator() }

                uiState.error != null -> Box(
                    Modifier.fillMaxSize().padding(combinedPadding),
                    contentAlignment = Alignment.Center
                ) { Text(uiState.error!!, color = MaterialTheme.colorScheme.error) }

                uiState.budgets.isEmpty() -> Box(
                    Modifier.fillMaxSize().padding(combinedPadding),
                    contentAlignment = Alignment.Center
                ) { Text("Ingen budsjetter", color = MaterialTheme.colorScheme.onSurfaceVariant) }

                else -> LazyColumn(contentPadding = combinedPadding) {
                    items(uiState.budgets) { budget ->
                        BudgetCard(budget = budget, onClick = {
                            selectedBudget = budget
                            selectedMonth = LocalDate.now().monthValue
                            viewModel.loadReport(budget.id)
                        })
                    }
                }
            }
        }
    } else {
        // ── Budget report ────────────────────────────────────────────────────
        val budget = selectedBudget!!
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("${budget.name} ${budget.year}") },
                    navigationIcon = {
                        IconButton(onClick = {
                            selectedBudget = null
                            viewModel.clearReport()
                        }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Tilbake")
                        }
                    }
                )
            }
        ) { scaffoldPadding ->
            val combinedPadding = PaddingValues(
                top = scaffoldPadding.calculateTopPadding(),
                bottom = innerPadding.calculateBottomPadding()
            )
            when {
                reportState.isLoading -> Box(
                    Modifier.fillMaxSize().padding(combinedPadding),
                    contentAlignment = Alignment.Center
                ) { CircularProgressIndicator() }

                reportState.error != null -> Box(
                    Modifier.fillMaxSize().padding(combinedPadding),
                    contentAlignment = Alignment.Center
                ) { Text(reportState.error!!, color = MaterialTheme.colorScheme.error) }

                reportState.report != null -> {
                    val report = reportState.report!!
                    val lines = report.lines
                    val revenueLines = lines.filter { it.accountType == "REVENUE" }
                    val expenseLines = lines.filter { it.accountType == "EXPENSE" }

                    @OptIn(ExperimentalFoundationApi::class)
                    LazyColumn(contentPadding = combinedPadding) {
                        // Sticky header — stays visible while scrolling
                        stickyHeader(key = "month-selector") {
                            Surface(
                                color = MaterialTheme.colorScheme.background,
                                shadowElevation = 2.dp
                            ) {
                                Column {
                                    MonthSelector(selectedMonth = selectedMonth, onMonthChange = { selectedMonth = it })
                                    HorizontalDivider()
                                }
                            }
                        }

                        if (revenueLines.isNotEmpty()) {
                            item(key = "header-revenue") { SectionHeader("Inntekter") }
                            items(revenueLines, key = { "rev-${it.accountId}" }) { line ->
                                AccountRow(line = line, month = selectedMonth, isRevenue = true)
                                HorizontalDivider(thickness = 0.5.dp)
                            }
                            item(key = "sum-revenue") {
                                SummaryRow(
                                    label = "Sum inntekter",
                                    budget = revenueLines.budgetSum(selectedMonth),
                                    actual = revenueLines.actualSum(selectedMonth),
                                    isRevenue = true
                                )
                                HorizontalDivider()
                            }
                        }

                        if (expenseLines.isNotEmpty()) {
                            item(key = "header-expense") { SectionHeader("Utgifter") }
                            items(expenseLines, key = { "exp-${it.accountId}" }) { line ->
                                AccountRow(line = line, month = selectedMonth, isRevenue = false)
                                HorizontalDivider(thickness = 0.5.dp)
                            }
                            item(key = "sum-expense") {
                                SummaryRow(
                                    label = "Sum utgifter",
                                    budget = expenseLines.budgetSum(selectedMonth),
                                    actual = expenseLines.actualSum(selectedMonth),
                                    isRevenue = false
                                )
                                HorizontalDivider()
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun List<BudgetReportLine>.budgetSum(month: Int?): Double =
    if (month == null) sumOf { it.totalBudget }
    else sumOf { it.months.firstOrNull { m -> m.month == month }?.budget ?: 0.0 }

private fun List<BudgetReportLine>.actualSum(month: Int?): Double =
    if (month == null) sumOf { it.totalActual }
    else sumOf { it.months.firstOrNull { m -> m.month == month }?.actual ?: 0.0 }

@Composable
private fun BudgetCard(budget: BudgetResponse, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp)
            .clickable { onClick() },
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(budget.name, style = MaterialTheme.typography.titleMedium)
            Text(
                budget.year.toString(),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun MonthSelector(selectedMonth: Int?, onMonthChange: (Int?) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        IconButton(onClick = {
            onMonthChange(
                when (selectedMonth) {
                    null -> 12
                    1 -> null
                    else -> selectedMonth - 1
                }
            )
        }) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Forrige")
        }

        TextButton(onClick = { onMonthChange(null) }) {
            Text(
                if (selectedMonth == null) "Hele året"
                else MONTH_NAMES[selectedMonth - 1],
                style = MaterialTheme.typography.titleSmall,
                fontWeight = if (selectedMonth == null) FontWeight.Bold else FontWeight.Normal
            )
        }

        IconButton(onClick = {
            onMonthChange(
                when (selectedMonth) {
                    null -> 1
                    12 -> null
                    else -> selectedMonth + 1
                }
            )
        }) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Neste")
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        title,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary
    )
}

@Composable
private fun AccountRow(line: BudgetReportLine, month: Int?, isRevenue: Boolean) {
    val monthData = if (month != null) line.months.firstOrNull { it.month == month } else null
    val budget = monthData?.budget ?: if (month == null) line.totalBudget else 0.0
    val actual = monthData?.actual ?: if (month == null) line.totalActual else 0.0
    val variance = actual - budget

    // For revenue: positive variance (more income than budgeted) is good
    // For expense: negative variance (less spending than budgeted) is good
    val varianceGood = if (isRevenue) variance >= 0 else variance <= 0
    val varianceColor = when {
        variance == 0.0 -> MaterialTheme.colorScheme.onSurface
        varianceGood -> Color(0xFF2E7D32)
        else -> MaterialTheme.colorScheme.error
    }

    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(Modifier.weight(1.4f)) {
            Text(line.accountName, style = MaterialTheme.typography.bodyMedium)
            Text(
                line.accountNumber,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        AmountCol(budget, Modifier.weight(1f))
        AmountCol(actual, Modifier.weight(1f))
        Text(
            formatAmount(variance),
            modifier = Modifier.weight(1f),
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodySmall,
            color = varianceColor
        )
    }
}

@Composable
private fun SummaryRow(label: String, budget: Double, actual: Double, isRevenue: Boolean) {
    val variance = actual - budget
    val varianceGood = if (isRevenue) variance >= 0 else variance <= 0
    val varianceColor = when {
        variance == 0.0 -> MaterialTheme.colorScheme.onSurface
        varianceGood -> Color(0xFF2E7D32)
        else -> MaterialTheme.colorScheme.error
    }
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            label,
            modifier = Modifier.weight(1.4f),
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold
        )
        Text(
            formatAmount(budget),
            modifier = Modifier.weight(1f),
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold
        )
        Text(
            formatAmount(actual),
            modifier = Modifier.weight(1f),
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold
        )
        Text(
            formatAmount(variance),
            modifier = Modifier.weight(1f),
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = varianceColor
        )
    }
}

@Composable
private fun AmountCol(amount: Double, modifier: Modifier = Modifier) {
    Text(
        formatAmount(amount),
        modifier = modifier,
        textAlign = TextAlign.End,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurface
    )
}

private fun formatAmount(amount: Double): String {
    if (amount == 0.0) return "0"
    return "%,.0f".format(amount).replace(',', ' ')
}
