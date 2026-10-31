package eu.privatregnskap.app.ui.transactions

import java.text.NumberFormat
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private val NB = Locale.forLanguageTag("nb-NO")
private val DAY = DateTimeFormatter.ofPattern("dd.MM.yyyy")
private val DAY_AND_TIME = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")

internal fun formatAmount(value: Double): String {
    val nf = NumberFormat.getNumberInstance(NB).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }
    return "${nf.format(value)} kr"
}

/** ISO date from the API as the Norwegian day-first form; unparsable text is left alone */
internal fun formatDate(iso: String): String =
    runCatching { LocalDate.parse(iso.take(10)).format(DAY) }.getOrDefault(iso)

internal fun formatDateTime(iso: String): String =
    runCatching { LocalDateTime.parse(iso.take(19)).format(DAY_AND_TIME) }
        .getOrElse { formatDate(iso) }

internal fun statusLabel(status: String): String = when (status) {
    "POSTED" -> "Bokført"
    "DRAFT" -> "Kladd"
    "RECONCILED" -> "Avstemt"
    else -> status
}

internal fun sourceLabel(source: String?): String = when (source) {
    "MANUAL" -> "Manuelt ført"
    "BANK_SYNC" -> "Banksynkronisering"
    "CSV_IMPORT" -> "CSV-import"
    null -> "Ukjent kilde"
    else -> source
}
