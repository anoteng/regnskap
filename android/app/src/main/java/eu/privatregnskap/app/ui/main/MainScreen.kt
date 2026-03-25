package eu.privatregnskap.app.ui.main

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import eu.privatregnskap.app.ui.attachments.AttachmentsScreen
import eu.privatregnskap.app.ui.dashboard.DashboardScreen
import eu.privatregnskap.app.ui.postingqueue.PostingQueueScreen
import eu.privatregnskap.app.ui.profile.ProfileScreen

private sealed class Tab(val route: String, val label: String, val icon: ImageVector) {
    object Dashboard : Tab("tab/dashboard", "Hjem", Icons.Default.Home)
    object PostingQueue : Tab("tab/posting-queue", "Posteringskø", Icons.Default.List)
    object Attachments : Tab("tab/attachments", "Vedlegg", Icons.Default.AttachFile)
    object Profile : Tab("tab/profile", "Profil", Icons.Default.AccountCircle)
}

private val tabs = listOf(Tab.Dashboard, Tab.PostingQueue, Tab.Attachments, Tab.Profile)

@Composable
fun MainScreen(onLogout: () -> Unit) {
    val navController = rememberNavController()
    val currentEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentEntry?.destination?.route

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { tab ->
                    NavigationBarItem(
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                        selected = currentRoute == tab.route,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Tab.Dashboard.route
        ) {
            composable(Tab.Dashboard.route) {
                DashboardScreen(innerPadding = padding)
            }
            composable(Tab.PostingQueue.route) {
                PostingQueueScreen(innerPadding = padding)
            }
            composable(Tab.Attachments.route) {
                AttachmentsScreen(innerPadding = padding)
            }
            composable(Tab.Profile.route) {
                ProfileScreen(onLogout = onLogout)
            }
        }
    }
}
