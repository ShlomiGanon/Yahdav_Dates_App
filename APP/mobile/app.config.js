// Dynamic Expo config (Expo's recommended approach for build-variant
// config) — replaces the previous static app.json. Production behavior is
// unchanged: IS_DEV_BUILD is false unless release-dev.yml's Android job
// explicitly sets EXPO_PUBLIC_RUNTIME_API_URL_ENABLED=true before running
// `expo prebuild` (see .github/workflows/release-dev.yml). release.yml's
// build-android never sets it, so production always falls through to the
// exact same values app.json used to hold.
const IS_DEV_BUILD = process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED === 'true';

module.exports = {
  expo: {
    name: IS_DEV_BUILD ? 'יחדיו (Dev)' : 'יחדיו',
    slug: 'yahdav',
    scheme: 'yahdav',
    version: '1.0.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    userInterfaceStyle: 'light',

    splash: {
      image: './assets/splash-icon.png',
      resizeMode: 'contain',
      backgroundColor: '#1A1A2E',
    },

    ios: {
      bundleIdentifier: IS_DEV_BUILD ? 'com.yahdav.app.dev' : 'com.yahdav.app',
      supportsTablet: false,
      infoPlist: {
        NSPhotoLibraryUsageDescription: 'נדרשת גישה לגלריה להעלאת תמונות פרופיל.',
        NSCameraUsageDescription: 'נדרשת גישה למצלמה לצילום תמונת פרופיל.',
      },
    },

    android: {
      package: IS_DEV_BUILD ? 'com.yahdav.app.dev' : 'com.yahdav.app',
      adaptiveIcon: {
        backgroundColor: '#1A1A2E',
        foregroundImage: './assets/android-icon-foreground.png',
        backgroundImage: './assets/android-icon-background.png',
        monochromeImage: './assets/android-icon-monochrome.png',
      },
      predictiveBackGestureEnabled: false,
      softwareKeyboardLayoutMode: 'resize',
      permissions: [
        'android.permission.READ_MEDIA_IMAGES',
        'android.permission.CAMERA',
      ],
    },

    web: {
      favicon: './assets/favicon.png',
    },

    plugins: [
      'expo-secure-store',
      'expo-image',
      'expo-font',
      [
        'expo-image-picker',
        {
          photosPermission: 'נדרשת גישה לגלריה להעלאת תמונות פרופיל.',
          cameraPermission: 'נדרשת גישה למצלמה לצילום תמונת פרופיל.',
        },
      ],
      [
        'expo-notifications',
        {
          icon: './assets/icon.png',
          color: '#C0392B',
          sounds: [],
        },
      ],
    ],

    extra: {
      eas: {
        projectId: 'REPLACE_WITH_EAS_PROJECT_ID',
      },
    },

    owner: 'REPLACE_WITH_EXPO_ACCOUNT_USERNAME',
  },
};
