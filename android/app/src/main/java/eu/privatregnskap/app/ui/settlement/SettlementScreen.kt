package eu.privatregnskap.app.ui.settlement

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.network.dto.SettlementMemberResult
import java.text.NumberFormat
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

private val NB = Locale.forLanguageTag("nb-NO")
private val DATE_FMT = DateTimeFormatter.ofPattern("d. MMM", NB)

fun formatKr(value: String?): String {
    val amount = value?.toDoubleOrNull() ?: 0.0
    val nf = NumberFormat.getNumberInstance(NB).apply {
        minimumFractionDigits = 0
        maximumFractionDigits = 0
    }
    return "${nf.format(amount)} kr"
}

fun monthLabel(month: YearMonth): String {
    val name = month.month.getDisplayName(TextStyle.FULL_STANDALONE, NB)
    return name.replaceFirstChar { it.uppercase(NB) } + " " + month.year
}

private fun formatDay(iso: String): String =
    runCatching { LocalDate.parse(iso).format(DATE_FMT) }.getOrDefault(iso)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettlementScreen(
    innerPadding: PaddingValues,
    onBack: () -> Unit,
    refreshKey: Int = 0,
    onSetUp: () -> Unit = {},
    viewModel: SettlementViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(refreshKey) {
        if (refreshKey > 0) viewModel.load()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Månedsavregning") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Tilbake")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.load() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Last på nytt")
                    }
                }
            )
        }
    ) { scaffoldPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(scaffoldPadding)
                .padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            MonthSelector(
                month = state.month,
                onPrevious = viewModel::previousMonth,
                onNext = viewModel::nextMonth,
                onToday = viewModel::currentMonth
            )

            Box(modifier = Modifier.fillMaxSize()) {
                when {
                    state.isLoading && state.calculation == null ->
                        CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))

                    state.error != null -> Text(
                        text = state.error!!,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.align(Alignment.Center).padding(24.dp)
                    )

                    !state.isEnabled -> Column(
                        modifier = Modifier.align(Alignment.Center).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "Månedsavregning er ikke aktivert for dette regnskapet ennå.",
                            textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = onSetUp) { Text("Sett opp nå") }
                    }

                    state.calculation != null -> SettlementContent(state.calculation!!)
                }
            }
        }
    }
}

@Composable
private fun MonthSelector(
    month: YearMonth,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onToday: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        IconButton(onClick = onPrevious) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Forrige måned")
        }
        Text(
            text = monthLabel(month),
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            modifier = Modifier.weight(1f)
        )
        IconButton(onClick = onNext) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Neste måned")
        }
        if (month != YearMonth.now()) {
            TextButton(onClick = onToday) { Text("I dag") }
        }
    }
}

@Composable
private fun SettlementContent(calc: SettlementCalculationResponse) {
    val t = calc.totals
    val remaining = listOf(t.plannedRemaining, t.recurringRemaining, t.variableRemaining)
        .sumOf { it.toDoubleOrNull() ?: 0.0 }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 16.dp)
    ) {
        item {
            Text(
                text = if (calc.monthComplete) "Måneden er avsluttet – tallene er faktiske."
                       else "Per ${formatDay(calc.asOf)} · ${calc.daysRemaining} dager igjen",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
        }

        item { SectionTitle("Deltakere") }
        items(calc.members, key = { it.userId }) { member -> MemberCard(member) }

        item {
            Text(
                text = "Anbefalt = andel av prognosen + egne uttak fra driftskontoen − innbetalt denne måneden.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
        }

        item { SectionTitle("Måneden") }
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    KeyValueRow("Bokført hittil", formatKr(t.booked), bold = true)
                    KeyValueRow("  herav fast", formatKr(t.bookedFixed), muted = true)
                    KeyValueRow("  herav variabelt", formatKr(t.bookedVariable), muted = true)
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    KeyValueRow("Gjenstår (anslag)", formatKr(remaining.toString()), bold = true)
                    KeyValueRow("  registrerte fakturaer", formatKr(t.plannedRemaining), muted = true)
                    KeyValueRow("  faste trekk", formatKr(t.recurringRemaining), muted = true)
                    KeyValueRow("  variabelt", formatKr(t.variableRemaining), muted = true)
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    KeyValueRow("Prognose for måneden", formatKr(t.forecastTotal), bold = true)
                    if ((t.excludedBooked.toDoubleOrNull() ?: 0.0) != 0.0) {
                        KeyValueRow("Holdt utenfor (ekskluderte kontoer)", formatKr(t.excludedBooked), muted = true)
                    }
                }
            }
        }

        if (calc.planned.isNotEmpty()) {
            item { SectionTitle("Registrerte fakturaer") }
            items(calc.planned, key = { "p${it.plannedTransactionId}" }) { line ->
                LineRow(
                    primary = line.description,
                    secondary = "Forfall ${formatDay(line.expectedDate)}" + if (line.overdue) " · forfalt" else "",
                    amount = formatKr(line.amount),
                    warn = line.overdue
                )
            }
        }

        if (calc.recurring.isNotEmpty()) {
            item { SectionTitle("Forventede faste trekk") }
            items(calc.recurring, key = { "r${it.key}" }) { line ->
                LineRow(
                    primary = line.description,
                    secondary = "ca. ${line.expectedDay}." +
                        if (line.periodMonths > 1) " · hver ${line.periodMonths}. måned" else "",
                    amount = formatKr(line.amount)
                )
            }
        }

        item { SectionTitle("Likviditet") }
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp)) {
                KeyValueRow("Driftskonto", calc.liquidity.operatingBalance?.let { formatKr(it) } ?: "–")
                calc.liquidity.creditCards.forEach { card ->
                    KeyValueRow("${card.name} utestående", formatKr(card.owed))
                }
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

@Composable
private fun KeyValueRow(label: String, value: String, bold: Boolean = false, muted: Boolean = false) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        val color = if (muted) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface
        val weight = if (bold) FontWeight.SemiBold else FontWeight.Normal
        Text(label, style = MaterialTheme.typography.bodyMedium, color = color, fontWeight = weight, modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyMedium, color = color, fontWeight = weight)
    }
}

@Composable
private fun LineRow(primary: String, secondary: String, amount: String, warn: Boolean = false) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(primary, style = MaterialTheme.typography.bodyMedium, maxLines = 1)
            Text(
                secondary,
                style = MaterialTheme.typography.bodySmall,
                color = if (warn) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Text(amount, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun MemberCard(member: SettlementMemberResult, compact: Boolean = false) {
    val transfer = member.recommendedTransfer.toDoubleOrNull() ?: 0.0
    val due = transfer > 0
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(member.fullName, style = MaterialTheme.typography.titleSmall)
                    Text(
                        "${member.sharePercent.toDoubleOrNull()?.let { fmtPercent(it) } ?: member.sharePercent} % andel",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        formatKr(kotlin.math.abs(transfer).toString()),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (due) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
                    )
                    Text(
                        if (due) "å overføre" else "til gode",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            if (!compact) {
                Spacer(modifier = Modifier.height(8.dp))
                KeyValueRow("Andel av prognose", formatKr(member.shareAmount), muted = true)
                KeyValueRow("Egne uttak", formatKr(member.ownWithdrawals), muted = true)
                KeyValueRow("Innbetalt", formatKr(member.contributed), muted = true)
            }
        }
    }
}

private fun fmtPercent(value: Double): String =
    if (value == value.toLong().toDouble()) value.toLong().toString()
    else String.format(NB, "%.2f", value)
