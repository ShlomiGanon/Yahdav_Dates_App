import React from 'react';
import { View, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

export function Divider() {
  return <View style={styles.divider} />;
}

const styles = StyleSheet.create({
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: theme.palette.offline,
    marginVertical: theme.spacing.xs,
  },
});
