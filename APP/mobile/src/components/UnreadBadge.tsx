import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

type Props = { count: number };

export function UnreadBadge({ count }: Props) {
  if (count <= 0) return null;
  return (
    <View style={styles.badge}>
      <Text style={styles.text}>{count > 99 ? '99+' : count}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: theme.palette.primary,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.xs,
  },
  text: {
    color: theme.palette.surface,
    fontSize: theme.type.small,
    fontWeight: 'bold',
    fontFamily: theme.fontFamily,
  },
});
