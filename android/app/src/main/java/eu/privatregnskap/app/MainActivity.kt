package eu.privatregnskap.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import androidx.core.content.IntentCompat
import dagger.hilt.android.AndroidEntryPoint
import eu.privatregnskap.app.ui.navigation.PrivatregnskapNavGraph
import eu.privatregnskap.app.ui.theme.PrivatregnskapTheme
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    @Inject lateinit var appLockManager: AppLockManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val sharedUri: Uri? = when (intent?.action) {
            Intent.ACTION_VIEW -> intent.data
            Intent.ACTION_SEND -> IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java)
            else -> null
        }

        setContent {
            PrivatregnskapTheme {
                Surface {
                    PrivatregnskapNavGraph(initialFileUri = sharedUri)
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        appLockManager.onAppForeground()
    }

    override fun onStop() {
        super.onStop()
        if (!isChangingConfigurations) {
            appLockManager.onAppBackground()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (!isChangingConfigurations) {
            appLockManager.onAppClosed()
        }
    }
}
