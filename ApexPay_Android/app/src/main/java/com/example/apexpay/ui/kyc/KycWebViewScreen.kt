package com.example.apexpay.ui.kyc

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class KycJsBridge(
    private val onComplete: (String) -> Unit
) {
    @JavascriptInterface
    fun postMessage(json: String) {
        onComplete(json)
    }

    @JavascriptInterface
    fun onKycComplete(json: String) {
        onComplete(json)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun KycWebViewScreen(
    url: String,
    onBack: () -> Unit,
    onVerificationComplete: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }
    var isLoading by remember { mutableStateOf(true) }

    // File chooser callback holder
    var filePathCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    var currentPhotoUri by remember { mutableStateOf<Uri?>(null) }

    // Camera capture contract
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

    // Gallery / document picker contract
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

    // Permission launcher for Camera & Mic
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val cameraGranted = permissions[Manifest.permission.CAMERA] ?: false
        val audioGranted = permissions[Manifest.permission.RECORD_AUDIO] ?: false
        if (cameraGranted) {
            Toast.makeText(context, "Camera permission granted", Toast.LENGTH_SHORT).show()
        }
    }

    LaunchedEffect(Unit) {
        permissionLauncher.launch(
            arrayOf(
                Manifest.permission.CAMERA,
                Manifest.permission.RECORD_AUDIO
            )
        )
    }

    fun createTempImageUri(ctx: Context): Uri? {
        return try {
            val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val storageDir = ctx.getExternalFilesDir(Environment.DIRECTORY_PICTURES)
            val file = File.createTempFile("KYC_${timeStamp}_", ".jpg", storageDir)
            FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", file)
        } catch (ex: IOException) {
            ex.printStackTrace()
            null
        }
    }

    Column(modifier = modifier.fillMaxSize().background(Color(0xFFF8FAFC))) {
        TopAppBar(
            title = {
                Column {
                    Text(
                        text = "Identity Verification",
                        fontSize = 16.sp,
                        color = Color(0xFF0F172A)
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .background(Color(0xFF10B981), shape = CircleShape)
                        )
                        Text(
                            text = " Secure KYC Hardware Channel",
                            fontSize = 11.sp,
                            color = Color(0xFF64748B)
                        )
                    }
                }
            },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = Color(0xFF0F172A)
                    )
                }
            },
            actions = {
                IconButton(onClick = { webViewInstance?.reload() }) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Refresh",
                        tint = Color(0xFF2563EB)
                    )
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = Color.White
            )
        )

        Box(modifier = Modifier.fillMaxSize()) {
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

                        // Connect JS interface for receiving KYC result notifications
                        addJavascriptInterface(
                            KycJsBridge { json ->
                                (context as? androidx.activity.ComponentActivity)?.runOnUiThread {
                                    val isSuccess = json.contains("completed") || json.contains("needs_review")
                                    onVerificationComplete(isSuccess)
                                }
                            },
                            "AndroidBridge"
                        )

                        webViewClient = object : WebViewClient() {
                            override fun onPageFinished(view: WebView?, url: String?) {
                                super.onPageFinished(view, url)
                                isLoading = false
                            }
                        }

                        webChromeClient = object : WebChromeClient() {
                            // Synchronously grant WebRTC camera and audio permissions to the page
                            override fun onPermissionRequest(request: PermissionRequest) {
                                request.grant(request.resources)
                            }

                            // Native Android Camera & File Chooser implementation
                            override fun onShowFileChooser(
                                webView: WebView?,
                                filePathCb: ValueCallback<Array<Uri>>?,
                                fileChooserParams: FileChooserParams?
                            ): Boolean {
                                filePathCallback?.onReceiveValue(null)
                                filePathCallback = filePathCb

                                val isCapture = fileChooserParams?.isCaptureEnabled == true
                                val acceptTypes = fileChooserParams?.acceptTypes ?: emptyArray()

                                if (isCapture) {
                                    val photoUri = createTempImageUri(ctx)
                                    if (photoUri != null) {
                                        currentPhotoUri = photoUri
                                        takePictureLauncher.launch(photoUri)
                                        return true
                                    }
                                }

                                // Fallback or general image picker
                                getContentLauncher.launch("image/*")
                                return true
                            }
                        }

                        webViewInstance = this
                        loadUrl(url)
                    }
                },
                modifier = Modifier.fillMaxSize()
            )

            if (isLoading) {
                Box(
                    modifier = Modifier.fillMaxSize().background(Color(0xFFF8FAFC)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = Color(0xFF2563EB))
                        Text(
                            text = "Initializing secure verification...",
                            color = Color(0xFF64748B),
                            fontSize = 13.sp,
                            modifier = Modifier.padding(top = 12.dp)
                        )
                    }
                }
            }
        }
    }
}
