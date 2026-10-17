const { withAndroidManifest, withInfoPlist, createRunOncePlugin } = require('@expo/config-plugins');

const CAMERA_USAGE = 'RyouU KYC requires camera access to capture your identity document and selfie for biometric verification.';
const MICROPHONE_USAGE = 'RyouU KYC requires microphone access for audio challenges and spoken verification.';

const withKycIosPermissions = (config, { cameraPermission, microphonePermission } = {}) => {
  return withInfoPlist(config, (modConfig) => {
    modConfig.modResults.NSCameraUsageDescription =
      cameraPermission || modConfig.modResults.NSCameraUsageDescription || CAMERA_USAGE;
    modConfig.modResults.NSMicrophoneUsageDescription =
      microphonePermission || modConfig.modResults.NSMicrophoneUsageDescription || MICROPHONE_USAGE;
    return modConfig;
  });
};

const withKycAndroidPermissions = (config) => {
  return withAndroidManifest(config, (modConfig) => {
    const androidManifest = modConfig.modResults;
    if (!androidManifest.manifest['uses-permission']) {
      androidManifest.manifest['uses-permission'] = [];
    }
    const permissions = [
      'android.permission.CAMERA',
      'android.permission.RECORD_AUDIO',
      'android.permission.MODIFY_AUDIO_SETTINGS',
    ];
    for (const perm of permissions) {
      if (!androidManifest.manifest['uses-permission'].some((p) => p.$['android:name'] === perm)) {
        androidManifest.manifest['uses-permission'].push({
          $: { 'android:name': perm },
        });
      }
    }
    return modConfig;
  });
};

const withUncloneKyc = (config, props = {}) => {
  config = withKycIosPermissions(config, props);
  config = withKycAndroidPermissions(config);
  return config;
};

module.exports = createRunOncePlugin(withUncloneKyc, '@unclone/kyc-react-native', '0.1.0');
