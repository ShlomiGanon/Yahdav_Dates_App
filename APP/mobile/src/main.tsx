// Must be the first import — gesture-handler patches the native event system
import 'react-native-gesture-handler';
import React from 'react';
import { I18nManager } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from './auth/AuthContext';
import { NetworkGuard } from './components/NetworkGuard';
import { ServerUrlGate } from './components/ServerUrlGate';
import { RootNavigator } from './navigation/RootNavigator';

// Force RTL layout engine for Hebrew — must run before any component renders
I18nManager.forceRTL(true);

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        {/* Dev builds only (EXPO_PUBLIC_RUNTIME_API_URL_ENABLED) — a plain
            passthrough in production, see ServerUrlGate.tsx. Sits above
            AuthProvider on purpose: AuthProvider's own boot-time API call
            must never fire before a working server URL is confirmed. */}
        <ServerUrlGate>
          <AuthProvider>
            <NetworkGuard>
              <RootNavigator />
            </NetworkGuard>
          </AuthProvider>
        </ServerUrlGate>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
