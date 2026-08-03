import React, { forwardRef, useImperativeHandle, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

export type StatusBannerRef = {
  showStatus: (message: string, ok: boolean) => void;
};

export const StatusBanner = forwardRef<StatusBannerRef>(function StatusBanner(_, ref) {
  const [state, setState] = useState<{ message: string; ok: boolean } | null>(null);

  useImperativeHandle(ref, () => ({
    showStatus(message, ok) {
      setState({ message, ok });
      setTimeout(() => setState(null), 3000);
    },
  }));

  if (!state) return null;

  return (
    <View style={[styles.banner, { backgroundColor: state.ok ? theme.palette.success : theme.palette.danger }]}>
      <Text style={styles.text}>{state.message}</Text>
    </View>
  );
});

const styles = StyleSheet.create({
  banner: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.radius.card,
    marginVertical: theme.spacing.xs,
  },
  text: {
    color: theme.palette.surface,
    fontSize: theme.type.body,
    fontWeight: 'bold',
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
});
