package eu.privatregnskap.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = SurfaceLight,
    primaryContainer = SurfaceRaisedLight,
    onPrimaryContainer = PrimaryDark,
    secondary = TextSecondaryLight,
    onSecondary = SurfaceLight,
    secondaryContainer = SurfaceRaisedLight,
    onSecondaryContainer = TextLight,
    background = BackgroundLight,
    onBackground = TextLight,
    surface = SurfaceLight,
    onSurface = TextLight,
    surfaceVariant = SurfaceRaisedLight,
    onSurfaceVariant = TextSecondaryLight,
    outline = BorderLight,
    error = Danger,
    onError = SurfaceLight
)

private val DarkColorScheme = darkColorScheme(
    primary = Primary,
    onPrimary = TextDark,
    primaryContainer = SurfaceRaisedDark,
    onPrimaryContainer = TextDark,
    secondary = TextSecondaryDark,
    onSecondary = BackgroundDark,
    secondaryContainer = SurfaceRaisedDark,
    onSecondaryContainer = TextDark,
    background = BackgroundDark,
    onBackground = TextDark,
    surface = SurfaceDark,
    onSurface = TextDark,
    surfaceVariant = SurfaceRaisedDark,
    onSurfaceVariant = TextSecondaryDark,
    outline = BorderDark,
    error = Danger,
    onError = TextDark
)

@Composable
fun PrivatregnskapTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography = PrivatregnskapTypography,
        content = content
    )
}
