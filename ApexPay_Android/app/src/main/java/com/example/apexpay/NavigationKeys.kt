package com.example.apexpay

import androidx.navigation3.runtime.NavKey
import kotlinx.serialization.Serializable

@Serializable
data object Main : NavKey

@Serializable
data class KycFlow(val flowUrl: String) : NavKey
