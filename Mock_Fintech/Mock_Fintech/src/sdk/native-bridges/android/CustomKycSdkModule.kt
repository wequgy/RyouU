package com.apexpay.fintech.sdk

import android.app.Activity
import android.content.Intent
import android.view.WindowManager
import com.facebook.react.bridge.ActivityEventListener
import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.BaseActivityEventListener
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.ReadableMap
import com.facebook.react.modules.core.DeviceEventManagerModule

/**
 * CustomKycSdkModule (Android Native Bridge Template)
 * 
 * Provides native bridge binding for proprietary Android KYC SDKs (.aar or Gradle dependency).
 * 
 * ANTI-SCREENCASTING / NETFLIX-GRADE DISPLAY SECURITY:
 * On Android, screencasting, Chromecast/Miracast mirroring, screen recording, and screenshots
 * are governed by the WindowManager FLAG_SECURE attribute.
 * When enabled on the Activity Window, the Android SurfaceFlinger hardware compositor replaces
 * the window content with solid black pixels in screencasts and video capture.
 */
class CustomKycSdkModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    private var activeKycPromise: Promise? = null
    private val KYC_REQUEST_CODE = 9021

    private val activityEventListener: ActivityEventListener = object : BaseActivityEventListener() {
        override fun onActivityResult(
            activity: Activity?,
            requestCode: Int,
            resultCode: Int,
            data: Intent?
        ) {
            if (requestCode == KYC_REQUEST_CODE) {
                activeKycPromise?.let { promise ->
                    if (resultCode == Activity.RESULT_OK && data != null) {
                        val map = Arguments.createMap().apply {
                            putString("status", "SUCCESS")
                            putString("verificationId", data.getStringExtra("VERIFICATION_ID") ?: "VERIF-SUCCESS")
                            putDouble("timestamp", System.currentTimeMillis().toDouble())
                        }
                        promise.resolve(map)
                    } else if (resultCode == Activity.RESULT_CANCELED) {
                        val map = Arguments.createMap().apply {
                            putString("status", "CANCELLED")
                            putString("failureReason", "Cancelled by user")
                        }
                        promise.resolve(map)
                    } else {
                        promise.reject("KYC_ERROR", "Verification failed or terminated")
                    }
                    activeKycPromise = null
                }
            }
        }
    }

    init {
        reactContext.addActivityEventListener(activityEventListener)
    }

    override fun getName(): String = "CustomKycNativeModule"

    /**
     * Enforces FLAG_SECURE on the Android Window.
     * Prevents screen recordings, screencasts, and screenshots across Android OS.
     */
    @ReactMethod
    fun enableScreenSecurity(promise: Promise) {
        val activity = currentActivity
        if (activity == null) {
            promise.reject("NO_ACTIVITY", "Current activity is null")
            return
        }

        activity.runOnUiThread {
            try {
                activity.window.setFlags(
                    WindowManager.LayoutParams.FLAG_SECURE,
                    WindowManager.LayoutParams.FLAG_SECURE
                )
                promise.resolve(true)
            } catch (e: Exception) {
                promise.reject("FLAG_SECURE_FAILED", e.localizedMessage)
            }
        }
    }

    /**
     * Releases FLAG_SECURE once sensitive KYC/SDK interaction is completed.
     */
    @ReactMethod
    fun disableScreenSecurity(promise: Promise) {
        val activity = currentActivity
        if (activity == null) {
            promise.reject("NO_ACTIVITY", "Current activity is null")
            return
        }

        activity.runOnUiThread {
            try {
                activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                promise.resolve(true)
            } catch (e: Exception) {
                promise.reject("CLEAR_FLAG_FAILED", e.localizedMessage)
            }
        }
    }

    /**
     * Launches the third-party or custom KYC native Activity.
     * 
     * [CUSTOM SDK INTEGRATION POINT]
     * Replace the Intent creation below with your custom SDK's launch invocation:
     * e.g., MyCustomKycSdk.Builder(activity)
     *         .setApiKey(apiKey)
     *         .setEnvironment(environment)
     *         .start(KYC_REQUEST_CODE)
     */
    @ReactMethod
    fun startNativeKycSession(options: ReadableMap, promise: Promise) {
        val activity = currentActivity
        if (activity == null) {
            promise.reject("NO_ACTIVITY", "Cannot launch KYC without active Activity")
            return
        }

        activeKycPromise = promise

        activity.runOnUiThread {
            try {
                // Ensure Window is secured before launching camera/KYC surface
                activity.window.setFlags(
                    WindowManager.LayoutParams.FLAG_SECURE,
                    WindowManager.LayoutParams.FLAG_SECURE
                )

                // Example Intent launch for custom SDK activity:
                // val intent = Intent(activity, Class.forName("com.yourcustomsdk.KycVerificationActivity"))
                // intent.putExtra("USER_ID", options.getString("userId"))
                // intent.putExtra("API_KEY", options.getString("apiKey"))
                // activity.startActivityForResult(intent, KYC_REQUEST_CODE)

                // For mock / demonstration purposes:
                val map = Arguments.createMap().apply {
                    putString("status", "SUCCESS")
                    putString("verificationId", "NATIVE-KYC-" + System.currentTimeMillis())
                }
                promise.resolve(map)
                activeKycPromise = null

            } catch (e: Exception) {
                promise.reject("NATIVE_SDK_INIT_ERROR", e.localizedMessage)
                activeKycPromise = null
            }
        }
    }
}
