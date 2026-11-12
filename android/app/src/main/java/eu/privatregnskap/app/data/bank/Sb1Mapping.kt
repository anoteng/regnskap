package eu.privatregnskap.app.data.bank

import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

private val OSLO: ZoneId = ZoneId.of("Europe/Oslo")

// Carried along in raw_data for later reference, minus what only makes sense
// inside the bank's own session
private val RAW_DATA_LEFT_OUT = listOf("id", "detailsUrl", "classificationInput", "accountKey")

/** The bank gives dates as midnight Norwegian time in epoch milliseconds. */
private fun JSONObject.day(key: String): LocalDate? {
    if (isNull(key)) return null
    val millis = optLong(key, 0L)
    if (millis <= 0L) return null
    return Instant.ofEpochMilli(millis).atZone(OSLO).toLocalDate()
}

/**
 * One transaction from SpareBank 1 in the form the upload endpoint takes, or
 * null when it is not ready to be sent.
 *
 * Only booked transactions go up. A pending one has a placeholder where the
 * id will be, and its date and text can still change; it is picked up by a
 * later sync once the bank has booked it.
 */
internal fun mapSb1Transaction(tx: JSONObject): JSONObject? {
    if (tx.text("bookingStatus") != "BOOKED") return null

    // Booked transactions carry an 18-digit id, pending ones a single digit
    val externalId = tx.text("nonUniqueId")
    if (externalId.length <= 5) return null

    val date = tx.day("date") ?: return null
    if (tx.isNull("amount")) return null
    val amount = runCatching {
        BigDecimal(tx.get("amount").toString()).setScale(2, RoundingMode.HALF_UP)
    }.getOrNull() ?: return null

    val description = tx.text("description")
        .ifBlank { tx.text("cleanedDescription") }
        .ifBlank { tx.text("typeText") }
        .take(2000)

    val out = JSONObject()
        .put("external_id", externalId.take(255))
        .put("transaction_date", date.toString())
        .put("booking_date", date.toString())
        // Sent as text so that no decimals are lost on the way; the sign is the bank's
        .put("amount", amount.toPlainString())
        // accountCurrency is the account's own. currencyCode is what the
        // purchase was made in, and the amount is not in that.
        .put("currency", tx.text("accountCurrency").takeIf { it.length == 3 } ?: "NOK")
        .put("description", description)

    tx.day("interestDate")?.let { out.put("value_date", it.toString()) }
    tx.text("kid").takeIf { it.isNotBlank() }?.let { out.put("reference", it.take(255)) }
    tx.text("remoteAccountName").takeIf { it.isNotBlank() }?.let { out.put("merchant_name", it.take(255)) }

    val raw = JSONObject(tx.toString())
    RAW_DATA_LEFT_OUT.forEach { raw.remove(it) }
    out.put("raw_data", raw)

    return out
}
