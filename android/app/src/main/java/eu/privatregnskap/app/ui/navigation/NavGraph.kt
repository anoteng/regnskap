package eu.privatregnskap.app.ui.navigation

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import eu.privatregnskap.app.ui.auth.AppLockViewModel
import eu.privatregnskap.app.ui.auth.AuthViewModel
import eu.privatregnskap.app.ui.auth.ForgotPasswordScreen
import eu.privatregnskap.app.ui.auth.LockScreen
import eu.privatregnskap.app.ui.auth.LoginScreen
import eu.privatregnskap.app.ui.main.MainScreen

sealed class Screen(val route: String) {
    object Login : Screen("auth/login")
    object ForgotPassword : Screen("auth/forgot-password")
    object Main : Screen("main")
    object Lock : Screen("lock")
}

@Composable
fun PrivatregnskapNavGraph(initialFileUri: Uri? = null) {
    val rootNavController = rememberNavController()
    val authViewModel: AuthViewModel = hiltViewModel()
    val appLockViewModel: AppLockViewModel = hiltViewModel()
    val isLoggedIn by authViewModel.isLoggedIn.collectAsStateWithLifecycle(initialValue = false)
    val isLocked by appLockViewModel.isLocked.collectAsStateWithLifecycle()

    val startDestination = if (isLoggedIn) Screen.Main.route else Screen.Login.route

    // Navigate to login whenever the session expires or user logs out
    LaunchedEffect(isLoggedIn) {
        if (!isLoggedIn) {
            val currentRoute = rootNavController.currentDestination?.route
            if (currentRoute != null && currentRoute != Screen.Login.route) {
                rootNavController.navigate(Screen.Login.route) {
                    popUpTo(0) { inclusive = true }
                }
            }
        }
    }

    // Navigate to lock screen when app is locked and user is logged in
    LaunchedEffect(isLoggedIn, isLocked) {
        if (isLoggedIn && isLocked) {
            val currentRoute = rootNavController.currentDestination?.route
            if (currentRoute != null && currentRoute != Screen.Lock.route) {
                rootNavController.navigate(Screen.Lock.route)
            }
        }
    }

    NavHost(navController = rootNavController, startDestination = startDestination) {
        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    appLockViewModel.unlock()
                    rootNavController.navigate(Screen.Main.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onNavigateToForgotPassword = {
                    rootNavController.navigate(Screen.ForgotPassword.route)
                }
            )
        }

        composable(Screen.ForgotPassword.route) {
            ForgotPasswordScreen(
                onBack = { rootNavController.popBackStack() }
            )
        }

        composable(Screen.Main.route) {
            MainScreen(
                initialFileUri = initialFileUri,
                onLogout = {
                    rootNavController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Main.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.Lock.route) {
            LockScreen(
                onUnlocked = {
                    appLockViewModel.unlock()
                    rootNavController.popBackStack()
                }
            )
        }
    }
}
