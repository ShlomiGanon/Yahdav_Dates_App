import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { RemoteImage } from './RemoteImage';
import { theme } from '../style/theme';

type Props = {
  src?: string | null;
  name?: string;
  diameter?: number;
  online?: boolean;
};

export function Avatar({ src, name = '', diameter = theme.sizing.avatarSm, online }: Props) {
  const initials = name.trim().charAt(0).toUpperCase() || '?';
  const radius = diameter / 2;

  return (
    <View style={{ width: diameter, height: diameter }}>
      {src ? (
        <RemoteImage
          uri={src}
          style={{ width: diameter, height: diameter, borderRadius: radius }}
          contentFit="cover"
        />
      ) : (
        <View style={[styles.initials, { width: diameter, height: diameter, borderRadius: radius }]}>
          <Text style={[styles.initialsText, { fontSize: diameter * 0.4 }]}>{initials}</Text>
        </View>
      )}
      {online !== undefined && (
        <View style={[styles.dot, online ? styles.onlineDot : styles.offlineDot]} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  initials: {
    backgroundColor: theme.palette.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  initialsText: {
    color: theme.palette.surface,
    fontWeight: 'bold',
    fontFamily: theme.fontFamily,
  },
  dot: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: theme.palette.surface,
  },
  onlineDot:  { backgroundColor: theme.palette.online },
  offlineDot: { backgroundColor: theme.palette.offline },
});
