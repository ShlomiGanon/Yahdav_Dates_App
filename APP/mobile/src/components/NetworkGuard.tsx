import React, { useEffect, useState, ReactNode } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { theme } from '../style/theme';

export function NetworkGuard({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState<boolean | null>(true);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setIsConnected(state.isConnected);
    });
    return unsubscribe;
  }, []);

  return (
    <View style={styles.container}>
      {children}
      {isConnected === false && (
        <View style={styles.overlay}>
          <Text style={styles.text}>אין חיבור לאינטרנט</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  overlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(0,0,0,0.80)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 999,
  },
  text: {
    color: theme.palette.surface,
    fontSize: theme.type.h2,
    fontWeight: 'bold',
  },
});
