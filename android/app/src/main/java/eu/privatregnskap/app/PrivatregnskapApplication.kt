package eu.privatregnskap.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class PrivatregnskapApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        val channel = NotificationChannel(
            POSTING_QUEUE_CHANNEL_ID,
            "Posteringskø",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Varsler om nye transaksjoner i posteringskøen"
        }
        val bankSyncChannel = NotificationChannel(
            BANK_SYNC_CHANNEL_ID,
            "Banksynk",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Varsler når synkroniseringen fra banken trenger en ny innlogging"
        }
        getSystemService(NotificationManager::class.java).apply {
            createNotificationChannel(channel)
            createNotificationChannel(bankSyncChannel)
        }
    }

    companion object {
        const val POSTING_QUEUE_CHANNEL_ID = "posting_queue"
        const val BANK_SYNC_CHANNEL_ID = "bank_sync"
    }
}
