import React from 'react';
import { Pressable, View, StyleSheet } from 'react-native';
import { Image } from 'expo-image';
import { MaterialIcons } from '@expo/vector-icons';
import { theme } from '../style/theme';

type Props = {
  uri: string;
  onPress?: () => void;
  showRemove?: boolean;
  onRemove?: () => void;
  size?: number;
};

export function PhotoTile({ uri, onPress, showRemove = false, onRemove, size = 100 }: Props) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [{ width: size, height: size }, pressed && styles.pressed]}
    >
      <Image
        source={{ uri }}
        style={{ width: size, height: size, borderRadius: theme.radius.card }}
        contentFit="cover"
      />
      {showRemove && (
        <Pressable onPress={onRemove} style={styles.removeBtn} hitSlop={8}>
          <MaterialIcons name="close" size={12} color={theme.palette.surface} />
        </Pressable>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressed:   { opacity: theme.opacity.hover },
  removeBtn: {
    position: 'absolute',
    top: 4,
    right: 4,
    backgroundColor: theme.palette.danger,
    borderRadius: 10,
    width: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
