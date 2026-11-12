package eu.privatregnskap.app.worker

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import eu.privatregnskap.app.MainActivity
import eu.privatregnskap.app.PrivatregnskapApplication.Companion.BANK_SYNC_CHANNEL_ID
import eu.privatregnskap.app.data.bank.BankSyncRepository
import eu.privatregnskap.app.data.bank.SyncOutcome

/**
 * Fetches from the bank and uploads in the background.
 *
 * Running regularly is also what keeps the bank login alive: it lapses after
 * sixty days without use.
 */
@HiltWorker
class BankSyncWorker @AssistedInject constructor(
    @Assisted private val context: Context,
    @Assisted workerParams: WorkerParameters,
    private val bankSync: BankSyncRepository
) : CoroutineWorker(context, workerParams) {

    override suspend fun doWork(): Result =
        when (val outcome = bankSync.syncAll()) {
            is SyncOutcome.NeedsLogin -> {
                // Reported once: from here on there is no login to lose
                showLoginNeeded()
                Result.success()
            }
            is SyncOutcome.Failed ->
                if (outcome.retryable && runAttemptCount < MAX_ATTEMPTS) Result.retry() else Result.success()
            else -> Result.success()
        }

    private fun showLoginNeeded() {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val text = "Innloggingen i banken er utløpt. Logg inn med BankID under Profil for å fortsette."
        val notification = NotificationCompat.Builder(context, BANK_SYNC_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Banksynk har stoppet")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        context.getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, notification)
    }

    companion object {
        const val WORK_NAME = "bank_sync"
        private const val NOTIFICATION_ID = 1002
        private const val MAX_ATTEMPTS = 3
    }
}
