import { useEffect, useState, useCallback } from 'react';
import { Platform } from 'react-native';
import * as ScreenCapture from 'expo-screen-capture';

export interface UseSecureDisplayOptions {
  enabled?: boolean;
  onScreenshotAttempt?: () => void;
  onScreenCaptureChange?: (isCaptured: boolean) => void;
}

export function useSecureDisplay(options: UseSecureDisplayOptions = {}) {
  const { enabled = true, onScreenshotAttempt, onScreenCaptureChange } = options;
  const [isSecureActive, setIsSecureActive] = useState(false);
  const [isCaptureDetected, setIsCaptureDetected] = useState(false);
  const [simulatedScreencast, setSimulatedScreencast] = useState(false);

  // Activates OS-level screen protection (FLAG_SECURE on Android)
  useEffect(() => {
    let isMounted = true;

    async function activateProtection() {
      if (!enabled) return;
      try {
        await ScreenCapture.preventScreenCaptureAsync();
        if (isMounted) {
          setIsSecureActive(true);
        }
      } catch (err) {
        console.warn('[SecureDisplay] Error activating screen capture prevention:', err);
      }
    }

    activateProtection();

    // Listen for screenshot attempts (triggers toast / audit event)
    const screenshotSubscription = ScreenCapture.addScreenshotListener(() => {
      console.warn('[SecureDisplay] Screenshot attempt detected on secured display!');
      if (onScreenshotAttempt) {
        onScreenshotAttempt();
      }
    });

    return () => {
      isMounted = false;
      screenshotSubscription.remove();
      ScreenCapture.allowScreenCaptureAsync().catch((err) => {
        console.warn('[SecureDisplay] Error clearing screen capture prevention:', err);
      });
      setIsSecureActive(false);
    };
  }, [enabled, onScreenshotAttempt]);

  // Toggle screencast simulation for dev / review testing
  const toggleScreencastSimulation = useCallback(() => {
    setSimulatedScreencast((prev) => {
      const next = !prev;
      if (onScreenCaptureChange) {
        onScreenCaptureChange(next);
      }
      return next;
    });
  }, [onScreenCaptureChange]);

  const activeCaptureState = isCaptureDetected || simulatedScreencast;

  return {
    isSecureActive,
    isCaptureDetected: activeCaptureState,
    simulatedScreencast,
    toggleScreencastSimulation,
    platform: Platform.OS,
  };
}
