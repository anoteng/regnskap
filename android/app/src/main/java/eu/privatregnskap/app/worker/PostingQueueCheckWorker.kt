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
import eu.privatregnskap.app.PrivatregnskapApplication.Companion.POSTING_QUEUE_CHANNEL_ID
import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.preferences.NotificationPreferences
import eu.privatregnskap.app.data.repository.TokenRepository
import kotlinx.coroutines.flow.first

@HiltWorker
class PostingQueueCheckWorker @AssistedInject constructor(
    @Assisted private val context: Context,
    @Assisted workerParams: WorkerParameters,
    private val apiService: ApiService,
    private val tokenRepository: TokenRepository,
    private val notificationPreferences: NotificationPreferences
) : CoroutineWorker(context, workerParams) {

    override suspend fun doWork(): Result {
        if (!notificationPreferences.queueNotificationsEnabled.first()) return Result.success()
        if (!tokenRepository.isLoggedIn()) return Result.success()

        return try {
            val ledgers = apiService.getLedgers()
            val ledgerId = ledgers.firstOrNull()?.id ?: return Result.success()
            val response = apiService.getPostingQueue(ledgerId = ledgerId, limit = 1)
            val newCount = response.total
            val lastCount = notificationPreferences.getLastQueueCount()

            if (newCount > lastCount) {
                showNotification(newCount)
            }
            notificationPreferences.setLastQueueCount(newCount)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun showNotification(count: Int) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val text = if (count == 1) "1 transaksjon venter i posteringskøen"
                   else "$count transaksjoner venter i posteringskøen"
        val notification = NotificationCompat.Builder(context, POSTING_QUEUE_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Posteringskø")
            .setContentText(text)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        context.getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, notification)
    }

    companion object {
        const val WORK_NAME = "posting_queue_check"
        private const val NOTIFICATION_ID = 1001
    }
}
