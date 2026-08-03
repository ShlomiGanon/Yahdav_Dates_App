import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { usersApi } from '../api/users';

export async function setupPushNotifications(): Promise<void> {
  if (Platform.OS === 'web') return;

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
  } catch {
    // Push token unavailable — non-critical; app continues without push
  }
}
