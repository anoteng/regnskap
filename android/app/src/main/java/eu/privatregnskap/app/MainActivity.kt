package eu.privatregnskap.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import dagger.hilt.android.AndroidEntryPoint
import eu.privatregnskap.app.ui.navigation.PrivatregnskapNavGraph
import eu.privatregnskap.app.ui.theme.PrivatregnskapTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            PrivatregnskapTheme {
                Surface {
                    PrivatregnskapNavGraph()
                }
            }
        }
    }
}
