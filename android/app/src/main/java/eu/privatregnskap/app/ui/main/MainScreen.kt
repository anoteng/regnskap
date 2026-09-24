package eu.privatregnskap.app.ui.main

import android.net.Uri
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.PieChart
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import eu.privatregnskap.app.ui.attachments.AttachmentsScreen
import eu.privatregnskap.app.ui.budget.BudgetScreen
import eu.privatregnskap.app.ui.dashboard.DashboardScreen
import eu.privatregnskap.app.ui.postingqueue.PostingQueueScreen
import eu.privatregnskap.app.ui.profile.ProfileScreen
import eu.privatregnskap.app.ui.settlement.SettlementScreen
import eu.privatregnskap.app.ui.settlement.SettlementSetupScreen

private sealed class Tab(val route: String, val label: String, val icon: ImageVector) {
    object Dashboard : Tab("tab/dashboard", "Hjem", Icons.Default.Home)
    object PostingQueue : Tab("tab/posting-queue", "Posteringskø", Icons.AutoMirrored.Filled.List)
    object Attachments : Tab("tab/attachments", "Vedlegg", Icons.Default.AttachFile)
    object Budget : Tab("tab/budget", "Budsjett", Icons.Default.PieChart)
    object Profile : Tab("tab/profile", "Profil", Icons.Default.AccountCircle)
}

private val tabs = listOf(Tab.Dashboard, Tab.PostingQueue, Tab.Attachments, Tab.Budget, Tab.Profile)

private const val SETTLEMENT_ROUTE = "settlement"
private const val SETTLEMENT_SETUP_ROUTE = "settlement/setup"

@Composable
fun MainScreen(onLogout: () -> Unit, initialFileUri: Uri? = null) {
    val navController = rememberNavController()
    val currentEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentEntry?.destination?.route
    // Bumped when the setup screen saves, so the screens behind it reload
    var settlementRefresh by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(initialFileUri) {
        if (initialFileUri != null) {
            navController.navigate(Tab.Attachments.route) { launchSingleTop = true }
        }
    }

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
                DashboardScreen(
                    innerPadding = padding,
                    refreshKey = settlementRefresh,
                    onOpenSettlement = { navController.navigate(SETTLEMENT_ROUTE) { launchSingleTop = true } },
                    onSetUpSettlement = { navController.navigate(SETTLEMENT_SETUP_ROUTE) { launchSingleTop = true } }
                )
            }
            composable(SETTLEMENT_ROUTE) {
                SettlementScreen(
                    innerPadding = padding,
                    refreshKey = settlementRefresh,
                    onBack = { navController.popBackStack() },
                    onSetUp = { navController.navigate(SETTLEMENT_SETUP_ROUTE) { launchSingleTop = true } }
                )
            }
            composable(SETTLEMENT_SETUP_ROUTE) {
                SettlementSetupScreen(
                    innerPadding = padding,
                    onBack = { navController.popBackStack() },
                    onSaved = {
                        settlementRefresh++
                        navController.popBackStack()
                    }
                )
            }
            composable(Tab.PostingQueue.route) {
                PostingQueueScreen(innerPadding = padding)
            }
            composable(Tab.Attachments.route) {
                AttachmentsScreen(innerPadding = padding, initialUri = initialFileUri)
            }
            composable(Tab.Budget.route) {
                BudgetScreen(innerPadding = padding)
            }
            composable(Tab.Profile.route) {
                ProfileScreen(onLogout = onLogout)
            }
        }
    }
}
