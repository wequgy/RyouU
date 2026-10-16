package com.example.apexpay

import android.widget.Toast
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.ui.NavDisplay
import com.example.apexpay.ui.dashboard.DashboardScreen
import com.example.apexpay.ui.kyc.KycWebViewScreen

@Composable
fun MainNavigation() {
    val context = LocalContext.current
    val backStack = rememberNavBackStack(Main)
    var isVerified by remember { mutableStateOf(false) }

    NavDisplay(
        backStack = backStack,
        onBack = { backStack.removeLastOrNull() },
        entryProvider = entryProvider {
            entry<Main> {
                DashboardScreen(
                    onStartKyc = { flowUrl ->
                        backStack.add(KycFlow(flowUrl))
                    },
                    isVerified = isVerified,
                    modifier = Modifier.safeDrawingPadding()
                )
            }
            entry<KycFlow> { destination ->
                KycWebViewScreen(
                    url = destination.flowUrl,
                    onBack = {
                        backStack.removeLastOrNull()
                    },
                    onVerificationComplete = { success ->
                        isVerified = success
                        backStack.removeLastOrNull()
                        if (success) {
                            Toast.makeText(
                                context,
                                "Identity Verification Completed Successfully!",
                                Toast.LENGTH_LONG
                            ).show()
                        } else {
                            Toast.makeText(
                                context,
                                "Verification was not approved. Please try again.",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    },
                    modifier = Modifier.safeDrawingPadding()
                )
            }
        }
    )
}
