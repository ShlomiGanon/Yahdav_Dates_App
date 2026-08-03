import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { theme } from '../style/theme';

type Props = { message: string };

export function ErrorCard({ message }: Props) {
  return (
    <View style={styles.card}>
      <MaterialIcons name="error-outline" size={theme.sizing.iconLg} color={theme.palette.danger} />
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(231,76,60,0.1)',
    borderRadius: theme.radius.card,
    padding: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  message: {
    flex: 1,
    fontSize: theme.type.body,
    color: theme.palette.danger,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
});
