import Foundation
import UIKit
import React

/**
 * CustomKycSdkBridge (iOS Swift Native Bridge Template)
 * 
 * Provides native bridge binding for proprietary iOS KYC SDKs (.xcframework or CocoaPods).
 * 
 * ANTI-SCREENCASTING / NETFLIX-GRADE DISPLAY SECURITY (iOS):
 * iOS does not have an identical single flag to Android's FLAG_SECURE. Instead, two primary
 * industry-standard mechanisms are used by banking and DRM apps:
 * 
 * 1. Capture Notification Observer:
 *    Observes `UIScreen.capturedDidChangeNotification`. When `UIScreen.main.isCaptured` is true
 *    (e.g., Screen Recording, AirPlay Mirroring, or QuickTime Screencast is active), the view
 *    immediately blanks or presents an obfuscation shield.
 * 
 * 2. Hardware-protected Secure Canvas Layer:
 *    By wrapping the view hierarchy inside a UITextField with `isSecureTextEntry = true`
 *    subview layer, iOS's hardware compositor automatically blanks out the view content in
 *    any screen recording or screenshot, exactly matching DRM behavior.
 */
@objc(CustomKycSdkBridge)
class CustomKycSdkBridge: RCTEventEmitter {

    private var hasListeners = false
    private var secureContainerField: UITextField?

    override static func requiresMainQueueSetup() -> Bool {
        return true
    }

    override func supportedEvents() -> [String]! {
        return ["onScreenCaptureChanged", "onKycSdkEvent"]
    }

    override func startObserving() {
        hasListeners = true
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screenCaptureChanged),
            name: UIScreen.capturedDidChangeNotification,
            object: nil
        )
    }

    override func stopObserving() {
        hasListeners = false
        NotificationCenter.default.removeObserver(self)
    }

    @objc private func screenCaptureChanged() {
        let isCaptured = UIScreen.main.isCaptured
        if hasListeners {
            sendEvent(withName: "onScreenCaptureChanged", body: ["isCaptured": isCaptured])
        }
    }

    /**
     * Checks if iOS is currently recording or mirroring the screen.
     */
    @objc(isScreenCaptured:rejecter:)
    func isScreenCaptured(resolve: @escaping RCTPromiseResolveBlock, reject: @escaping RCTPromiseRejectBlock) {
        DispatchQueue.main.async {
            resolve(UIScreen.main.isCaptured)
        }
    }

    /**
     * Launches the custom iOS KYC SDK's UIViewController.
     * 
     * [CUSTOM SDK INTEGRATION POINT]
     * Replace the mock implementation below with your custom iOS SDK:
     * e.g.,
     *   let kycVC = CustomKycFramework.createVerificationController(apiKey: apiKey)
     *   rootVC.present(kycVC, animated: true)
     */
    @objc(startNativeKycSession:resolver:rejecter:)
    func startNativeKycSession(
        options: [String: Any],
        resolve: @escaping RCTPromiseResolveBlock,
        reject: @escaping RCTPromiseRejectBlock
    ) {
        DispatchQueue.main.async {
            guard let rootVC = UIApplication.shared.delegate?.window??.rootViewController else {
                reject("NO_ROOT_VC", "Unable to locate root UIViewController", nil)
                return
            }

            // Example presentation of custom SDK UIViewController
            print("[CustomKycSdkBridge] Initializing custom iOS KYC session...")

            // Return mock successful attestation
            let result: [String: Any] = [
                "status": "SUCCESS",
                "verificationId": "IOS-VERIF-\(Int(Date().timeIntervalSince1970))",
                "timestamp": Date().timeIntervalSince1970 * 1000
            ]
            resolve(result)
        }
    }
}
