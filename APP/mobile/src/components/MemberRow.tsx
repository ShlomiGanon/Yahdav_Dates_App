import React, { ReactNode } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Avatar } from './Avatar';
import { theme } from '../style/theme';

type Props = {
  src?: string | null;
  name: string;
  subtitle?: string;
  timestamp?: string;
  onPress: () => void;
  trailing?: ReactNode;
};

export function MemberRow({ src, name, subtitle, timestamp, onPress, trailing }: Props) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      {/* In RTL mode, first child renders on the right — avatar stays on the right side */}
      <Avatar src={src} name={name} diameter={theme.sizing.avatarLg} />
      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={1}>{name}</Text>
        {subtitle && <Text style={styles.subtitle} numberOfLines={1}>{subtitle}</Text>}
      </View>
      {(timestamp || trailing) && (
        <View style={styles.meta}>
          {timestamp && <Text style={styles.timestamp}>{timestamp}</Text>}
          {trailing && <View>{trailing}</View>}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    backgroundColor: theme.palette.surface,
    borderRadius: theme.radius.card,
    marginBottom: theme.spacing.xs,
    gap: theme.spacing.sm,
  },
  pressed:   { opacity: theme.opacity.hover },
  info:      { flex: 1 },
  name: {
    fontSize: theme.type.body,
    fontWeight: 'bold',
    color: theme.palette.textMain,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  subtitle: {
    fontSize: theme.type.small,
    color: theme.palette.offline,
    textAlign: 'right',
    marginTop: theme.spacing.xs,
    fontFamily: theme.fontFamily,
  },
  meta: {
    alignItems: 'flex-end',
    gap: theme.spacing.xs,
  },
  timestamp: {
    fontSize: theme.type.caption,
    color: theme.palette.offline,
    fontFamily: theme.fontFamily,
  },
});
