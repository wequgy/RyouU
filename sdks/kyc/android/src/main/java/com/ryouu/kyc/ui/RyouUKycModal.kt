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

import androidx.compose.runtime.saveable.rememberSaveable

object KycPickerHolder {
    var callback: ValueCallback<Array<Uri>>? = null
    var photoUri: Uri? = null
}

object KycWebViewHolder {
    var webView: WebView? = null
    fun clear() {
        try {
            webView?.destroy()
        } catch (_: Exception) {}
        webView = null
    }
}

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

    var activeRefId by rememberSaveable { mutableStateOf<String?>(null) }
    var verificationId by rememberSaveable { mutableStateOf<String?>(null) }
    var flowUrl by rememberSaveable { mutableStateOf<String?>(null) }
    var isLoadingSession by rememberSaveable { mutableStateOf(true) }
    var isPollingVerdict by rememberSaveable { mutableStateOf(false) }
    var currentPhotoUriString by rememberSaveable { mutableStateOf<String?>(null) }
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }

    // File chooser support with holder to survive background activity recreation
    var filePathCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }

    val takePictureLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        val cb = KycPickerHolder.callback ?: filePathCallback
        val uri = KycPickerHolder.photoUri ?: currentPhotoUriString?.let { Uri.parse(it) }
        if (cb != null) {
            if (success && uri != null) {
                cb.onReceiveValue(arrayOf(uri))
            } else {
                cb.onReceiveValue(null)
            }
            KycPickerHolder.callback = null
            filePathCallback = null
        }
    }

    val getContentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        val cb = KycPickerHolder.callback ?: filePathCallback
        if (cb != null) {
            if (uri != null) {
                cb.onReceiveValue(arrayOf(uri))
            } else {
                cb.onReceiveValue(null)
            }
            KycPickerHolder.callback = null
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

    var initError by remember { mutableStateOf<String?>(null) }
    var retryCount by remember { mutableStateOf(0) }

    fun handleCancel() {
        KycWebViewHolder.clear()
        flowUrl = null
        verificationId = null
        onCancel()
    }

    // Reset session whenever a new referenceId is passed
    LaunchedEffect(visible, params.referenceId) {
        if (!visible) {
            KycWebViewHolder.clear()
            return@LaunchedEffect
        }
        if (activeRefId != params.referenceId) {
            activeRefId = params.referenceId
            verificationId = null
            flowUrl = null
            isLoadingSession = true
            isPollingVerdict = false
            initError = null
            KycWebViewHolder.clear()
        }
    }

    // Trigger permission request and session creation
    LaunchedEffect(visible, config.backendUrl, params.referenceId, retryCount) {
        if (!visible) return@LaunchedEffect
        if (flowUrl != null && activeRefId == params.referenceId) {
            isLoadingSession = false
            return@LaunchedEffect
        }

        permissionLauncher.launch(
            arrayOf(
                Manifest.permission.CAMERA,
                Manifest.permission.RECORD_AUDIO
            )
        )

        try {
            isLoadingSession = true
            initError = null
            val (vId, url) = apiClient.createSession(config, params)
            verificationId = vId
            flowUrl = url
            activeRefId = params.referenceId
            isLoadingSession = false
        } catch (t: Throwable) {
            isLoadingSession = false
            initError = t.message ?: "Failed to connect to verification server"
            onError?.invoke(t)
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
                KycWebViewHolder.clear()
                flowUrl = null
                verificationId = null
                onComplete(result)
            } catch (t: Throwable) {
                isPollingVerdict = false
                KycWebViewHolder.clear()
                flowUrl = null
                verificationId = null
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
                                    .background(Color(0xFF65A30D), shape = CircleShape)
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
                    IconButton(onClick = ::handleCancel) {
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
                            val existing = KycWebViewHolder.webView
                            if (existing != null) {
                                (existing.parent as? ViewGroup)?.removeView(existing)
                                existing
                            } else {
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
                                            KycPickerHolder.callback?.onReceiveValue(null)
                                            KycPickerHolder.callback = filePathCb
                                            filePathCallback = filePathCb

                                            val isCapture = fileChooserParams?.isCaptureEnabled == true
                                            if (isCapture) {
                                                val photoUri = createTempImageUri(ctx)
                                                if (photoUri != null) {
                                                    KycPickerHolder.photoUri = photoUri
                                                    currentPhotoUriString = photoUri.toString()
                                                    takePictureLauncher.launch(photoUri)
                                                    return true
                                                }
                                            }

                                            getContentLauncher.launch("image/*")
                                            return true
                                        }
                                    }

                                    webViewInstance = this
                                    KycWebViewHolder.webView = this
                                    loadUrl(flowUrl!!)
                                }
                            }
                        },
                        update = { wv ->
                            if (wv.url == null && flowUrl != null) {
                                wv.loadUrl(flowUrl!!)
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
                            CircularProgressIndicator(color = Color(0xFF65A30D))
                            Spacer(modifier = Modifier.height(14.dp))
                            Text(
                                text = "Initializing secure KYC session...",
                                color = Color(0xFF64748B),
                                fontSize = 14.sp
                            )
                        }
                    }
                }

                // Error indicator with Retry button
                if (initError != null && !isLoadingSession && flowUrl == null) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.White)
                            .padding(28.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(
                                modifier = Modifier
                                    .size(60.dp)
                                    .background(Color(0xFFFEE2E2), shape = CircleShape),
                                contentAlignment = Alignment.Center
                            ) {
                                Text("⚠", fontSize = 28.sp, color = Color(0xFFDC2626))
                            }
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "Unable to Connect to Server",
                                fontSize = 17.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF0F172A)
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = initError ?: "Failed to reach customer backend at ${config.backendUrl}",
                                fontSize = 13.sp,
                                color = Color(0xFF64748B),
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                                lineHeight = 18.sp
                            )
                            Spacer(modifier = Modifier.height(24.dp))
                            androidx.compose.material3.Button(
                                onClick = {
                                    initError = null
                                    retryCount++
                                },
                                modifier = Modifier.fillMaxWidth().height(48.dp),
                                shape = RoundedCornerShape(9999.dp),
                                colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                                    containerColor = Color(0xFF65A30D)
                                )
                            ) {
                                Text("Retry Connection", fontWeight = FontWeight.Bold, color = Color.White)
                            }
                            Spacer(modifier = Modifier.height(10.dp))
                            androidx.compose.material3.OutlinedButton(
                                onClick = ::handleCancel,
                                modifier = Modifier.fillMaxWidth().height(44.dp),
                                shape = RoundedCornerShape(9999.dp)
                            ) {
                                Text("Close", color = Color(0xFF64748B))
                            }
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
                                color = Color(0xFF65A30D),
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
