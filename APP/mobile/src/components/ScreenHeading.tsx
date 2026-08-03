import React from 'react';
import { Text, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

type Props = { children: string };

export function ScreenHeading({ children }: Props) {
  return <Text style={styles.heading}>{children}</Text>;
}

const styles = StyleSheet.create({
  heading: {
    fontSize: theme.type.h1,
    fontWeight: 'bold',
    color: theme.palette.textMain,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
});
