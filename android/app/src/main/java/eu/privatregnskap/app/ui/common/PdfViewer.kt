package eu.privatregnskap.app.ui.common

import android.graphics.Bitmap
import android.graphics.Color as AndroidColor
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

/** Width in pixels each page is rendered at — sharp when zoomed, ~9 MB per A4 page. */
private const val RENDER_WIDTH = 1240

/**
 * Shows a local PDF file page by page.
 *
 * Pages are rendered one at a time as they scroll into view, so a long invoice
 * does not allocate every page up front. PdfRenderer is part of the framework,
 * so this needs no extra dependency.
 */
@Composable
fun PdfViewer(file: File, onDismiss: () -> Unit) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }

    val renderer = remember(file) { openRenderer(file) }
    DisposableEffect(renderer) {
        onDispose { renderer?.close() }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            if (renderer == null) {
                Text(
                    text = "Kunne ikke lese PDF-filen",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.Center).padding(24.dp)
                )
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .pointerInput(Unit) {
                            detectTransformGestures { _, pan, zoom, _ ->
                                scale = (scale * zoom).coerceIn(1f, 6f)
                                if (scale > 1f) {
                                    offsetX += pan.x
                                    offsetY += pan.y
                                } else {
                                    offsetX = 0f
                                    offsetY = 0f
                                }
                            }
                        }
                        .graphicsLayer(
                            scaleX = scale,
                            scaleY = scale,
                            translationX = offsetX,
                            translationY = offsetY
                        ),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(renderer.pageCount) { index ->
                        PdfPage(renderer, index)
                    }
                }
            }

            IconButton(
                onClick = onDismiss,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp)
            ) {
                Icon(Icons.Default.Close, contentDescription = "Lukk", tint = Color.White)
            }
        }
    }
}

@Composable
private fun PdfPage(renderer: PdfRenderer, index: Int) {
    val bitmap by produceState<Bitmap?>(initialValue = null, renderer, index) {
        // PdfRenderer allows only one open page at a time across the process
        value = withContext(Dispatchers.IO) { renderMutex.withLock { renderPage(renderer, index) } }
    }

    val page = bitmap
    if (page == null) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(0.707f),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(color = Color.White)
        }
    } else {
        Image(
            bitmap = page.asImageBitmap(),
            contentDescription = "Side ${index + 1}",
            modifier = Modifier.fillMaxWidth()
        )
    }
}

private val renderMutex = Mutex()

private fun openRenderer(file: File): PdfRenderer? = runCatching {
    PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY))
}.getOrNull()

private fun renderPage(renderer: PdfRenderer, index: Int): Bitmap? = runCatching {
    renderer.openPage(index).use { page ->
        val height = (RENDER_WIDTH.toFloat() / page.width * page.height).toInt().coerceAtLeast(1)
        val bitmap = Bitmap.createBitmap(RENDER_WIDTH, height, Bitmap.Config.ARGB_8888)
        // PDFs assume a white page; without this, transparent areas render black
        bitmap.eraseColor(AndroidColor.WHITE)
        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
        bitmap
    }
}.getOrNull()
