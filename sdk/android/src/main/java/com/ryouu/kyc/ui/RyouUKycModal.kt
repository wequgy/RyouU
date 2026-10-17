package com.ryouu.kyc.ui

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import com.ryouu.kyc.model.KycConfig
import com.ryouu.kyc.model.KycParams
import com.ryouu.kyc.model.KycResult
import com.ryouu.kyc.model.KycStatus
import com.ryouu.kyc.net.KycApiClient
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class KycJsBridge(
    private val onMessageReceived: (String) -> Unit
) {
    @JavascriptInterface
    fun postMessage(json: String) {
        onMessageReceived(json)
    }

    @JavascriptInterface
    fun onKycComplete(json: String) {
        onMessageReceived(json)
    }
}

/**
 * Reusable RyouU KYC verification modal for Jetpack Compose applications.
 *
 * It manages:
 * 1. Hardware permission requests (Camera & Audio).
 * 2. Secure session initiation with the customer backend (no secret key in client).
 * 3. In-app hardware-accelerated WebView execution.
 * 4. Listening for `kyc.done` postMessages.
 * 5. Polling the customer backend for the authentic server verdict.
 * 6. Returning the verified KycResult to [onComplete].
 */
@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun RyouUKycModal(
    visible: Boolean,
    config: KycConfig,
    params: KycParams,
    onComplete: (KycResult) -> Unit,
    onCancel: () -> Unit,
    onError: ((Throwable) -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    if (!visible) return

    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val apiClient = remember { KycApiClient() }

    var verificationId by remember { mutableStateOf<String?>(null) }
    var flowUrl by remember { mutableStateOf<String?>(null) }
    var isLoadingSession by remember { mutableStateOf(true) }
    var isPollingVerdict by remember { mutableStateOf(false) }
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }

    // File chooser support
    var filePathCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    var currentPhotoUri by remember { mutableStateOf<Uri?>(null) }

    val takePictureLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        val cb = filePathCallback
        if (cb != null) {
            if (success && currentPhotoUri != null) {
                cb.onReceiveValue(arrayOf(currentPhotoUri!!))
            } else {
                cb.onReceiveValue(null)
            }
            filePathCallback = null
        }
    }

    val getContentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        val cb = filePathCallback
        if (cb != null) {
            if (uri != null) {
                cb.onReceiveValue(arrayOf(uri))
            } else {
                cb.onReceiveValue(null)
            }
            filePathCallback = null
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    fun createTempImageUri(ctx: Context): Uri? {
        return try {
            val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val storageDir = ctx.getExternalFilesDir(Environment.DIRECTORY_PICTURES)
            val file = File.createTempFile("KYC_${timeStamp}_", ".jpg", storageDir)
            FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", file)
        } catch (ex: IOException) {
            null
        }
    }

    // Trigger permission request and session creation
    LaunchedEffect(visible, config.backendUrl, params.referenceId) {
        permissionLauncher.launch(
            arrayOf(
                Manifest.permission.CAMERA,
                Manifest.permission.RECORD_AUDIO
            )
        )

        try {
            isLoadingSession = true
            val (vId, url) = apiClient.createSession(config, params)
            verificationId = vId
            flowUrl = url
            isLoadingSession = false
        } catch (t: Throwable) {
            isLoadingSession = false
            onError?.invoke(t)
            onCancel()
        }
    }

    fun handleKycDone(vidFromMsg: String?) {
        val targetVid = vidFromMsg ?: verificationId ?: return
        if (isPollingVerdict) return
        isPollingVerdict = true

        scope.launch {
            try {
                val result = apiClient.pollVerdict(config, targetVid)
                isPollingVerdict = false
                onComplete(result)
            } catch (t: Throwable) {
                isPollingVerdict = false
                onError?.invoke(t)
                onCancel()
            }
        }
    }

    Surface(
        modifier = modifier.fillMaxSize(),
        color = Color(0xFFF8FAFC)
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // Header bar
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "RyouU Identity Verification",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF0F172A)
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .background(Color(0xFF10B981), shape = CircleShape)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Protected Biometric Hardware Channel",
                                fontSize = 11.sp,
                                color = Color(0xFF64748B)
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onCancel) {
                        Text(
                            text = "✕",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF64748B)
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White)
            )

            Box(modifier = Modifier.fillMaxSize()) {
                if (flowUrl != null && !isPollingVerdict) {
                    AndroidView(
                        factory = { ctx ->
                            WebView(ctx).apply {
                                layoutParams = ViewGroup.LayoutParams(
                                    ViewGroup.LayoutParams.MATCH_PARENT,
                                    ViewGroup.LayoutParams.MATCH_PARENT
                                )

                                settings.apply {
                                    javaScriptEnabled = true
                                    domStorageEnabled = true
                                    allowFileAccess = true
                                    allowContentAccess = true
                                    mediaPlaybackRequiresUserGesture = false
                                    mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                                    useWideViewPort = true
                                    loadWithOverviewMode = true
                                    setSupportZoom(false)
                                }

                                addJavascriptInterface(
                                    KycJsBridge { json ->
                                        try {
                                            val obj = JSONObject(json)
                                            val type = obj.optString("type", "")
                                            val vid = obj.optString("vid", "")
                                            if (type == "kyc.done" || type == "kyc_complete" || type == "kyc_submitted") {
                                                post { handleKycDone(vid.ifBlank { null }) }
                                            }
                                        } catch (e: Exception) {
                                            if (json.contains("kyc.done") || json.contains("completed")) {
                                                post { handleKycDone(null) }
                                            }
                                        }
                                    },
                                    "AndroidBridge"
                                )

                                webViewClient = object : WebViewClient() {}

                                webChromeClient = object : WebChromeClient() {
                                    override fun onPermissionRequest(request: PermissionRequest) {
                                        request.grant(request.resources)
                                    }

                                    override fun onShowFileChooser(
                                        webView: WebView?,
                                        filePathCb: ValueCallback<Array<Uri>>?,
                                        fileChooserParams: FileChooserParams?
                                    ): Boolean {
                                        filePathCallback?.onReceiveValue(null)
                                        filePathCallback = filePathCb

                                        val isCapture = fileChooserParams?.isCaptureEnabled == true
                                        if (isCapture) {
                                            val photoUri = createTempImageUri(ctx)
                                            if (photoUri != null) {
                                                currentPhotoUri = photoUri
                                                takePictureLauncher.launch(photoUri)
                                                return true
                                            }
                                        }

                                        getContentLauncher.launch("image/*")
                                        return true
                                    }
                                }

                                webViewInstance = this
                                loadUrl(flowUrl!!)
                            }
                        },
                        modifier = Modifier.fillMaxSize()
                    )
                }

                // Loading session indicator
                if (isLoadingSession) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color(0xFFF8FAFC)),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = Color(0xFF2563EB))
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = "Initializing secure KYC session...",
                                color = Color(0xFF64748B),
                                fontSize = 14.sp
                            )
                        }
                    }
                }

                // Polling authentic verdict indicator
                if (isPollingVerdict) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.White),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            CircularProgressIndicator(
                                color = Color(0xFF10B981),
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(modifier = Modifier.height(18.dp))
                            Text(
                                text = "Verifying biometric credentials...",
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF0F172A)
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "Polling customer backend for authentic cryptographic verdict.",
                                fontSize = 13.sp,
                                color = Color(0xFF64748B)
                            )
                        }
                    }
                }
            }
        }
    }
}
