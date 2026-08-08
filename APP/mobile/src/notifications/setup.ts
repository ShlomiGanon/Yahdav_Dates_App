import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { usersApi } from '../api/users';

// Android 8+ requires a notification channel to exist before a notification
// can be displayed at all. Must run before any push can be received —
// called at the top of setupPushNotifications(), ahead of permission
// requests and token registration.
async function ensureAndroidNotificationChannel(): Promise<void>
{
  if (Platform.OS !== 'android')
  {
    return;
  }

  await Notifications.setNotificationChannelAsync('messages', {
    name: 'הודעות',
    description: 'התראות על הודעות חדשות שהתקבלו באפליקציה',
    importance: Notifications.AndroidImportance.HIGH,
  });
}

export async function setupPushNotifications(): Promise<void> {
  if (Platform.OS === 'web') return;

  await ensureAndroidNotificationChannel();

  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert:  true,
      shouldShowBanner: true,
      shouldShowList:   true,
      shouldPlaySound:  true,
      shouldSetBadge:   true,
    }),
  });

  const { status: existing } = await Notifications.getPermissionsAsync();
  const { status } =
    existing === 'granted'
      ? { status: existing }
      : await Notifications.requestPermissionsAsync();

  if (status !== 'granted') return;

  try {
    const tokenData = await Notifications.getExpoPushTokenAsync();
    await usersApi.registerPushToken(tokenData.data, Platform.OS);
  } catch (error) {
    // Push token unavailable — non-critical; app continues without push.
    // Logged so the actual failure (e.g. bad EAS project ID, network error)
    // is diagnosable from device logs without needing a code read.
    console.error('[push] failed to register push token:', error);
  }
}
