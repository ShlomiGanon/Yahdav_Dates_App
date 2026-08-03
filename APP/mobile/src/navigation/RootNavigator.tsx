import React, { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import * as Notifications from 'expo-notifications';
import { useAuth } from '../auth/AuthContext';
import { usePushToken } from '../notifications/usePushToken';
import { AuthStack } from './AuthStack';
import { MainStack } from './MainStack';
import { navigationRef, navigateToChat } from './navigationRef';
import { theme } from '../style/theme';

type NotifData = { peer_id?: string; peer_name?: string };

function extractChatParams(response: Notifications.NotificationResponse | null): NotifData {
  if (!response) return {};
  return (response.notification.request.content.data ?? {}) as NotifData;
}

// Static background shared across all screens — same effect as Flet's ft.Hero trick.
// Replace View with ImageBackground + require('../../assets/BG.png') when BG asset is ready.
export function RootNavigator() {
  const { user, isLoading } = useAuth();
  usePushToken();

  useEffect(() => {
    // Tap while app is foregrounded or backgrounded
    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      const { peer_id, peer_name } = extractChatParams(response);
      if (peer_id) navigateToChat(peer_id, peer_name ?? '');
    });

    // Tap that cold-started the app
    Notifications.getLastNotificationResponseAsync().then((response) => {
      const { peer_id, peer_name } = extractChatParams(response);
      if (peer_id) navigateToChat(peer_id, peer_name ?? '');
    });

    return () => sub.remove();
  }, []);

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={theme.palette.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.bg, { backgroundColor: theme.palette.background }]}>
      <NavigationContainer ref={navigationRef}>
        {user ? <MainStack /> : <AuthStack />}
      </NavigationContainer>
    </View>
  );
}

const styles = StyleSheet.create({
  bg:      { flex: 1 },
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center',
             backgroundColor: theme.palette.background },
});
