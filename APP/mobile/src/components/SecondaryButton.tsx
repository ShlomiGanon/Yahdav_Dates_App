import React, { useRef } from 'react';
import { Animated, Pressable, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

type Props = {
  text: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
};

const SPRING = { useNativeDriver: true, speed: 50, bounciness: 2 } as const;

export function SecondaryButton({ text, onPress, disabled = false, loading = false }: Props) {
  const scale      = useRef(new Animated.Value(1)).current;
  const isDisabled = disabled || loading;

  const pressIn  = () => Animated.spring(scale, { toValue: 0.96, ...SPRING }).start();
  const pressOut = () => Animated.spring(scale, { toValue: 1,    ...SPRING }).start();

  return (
    <Animated.View style={[styles.wrap, { transform: [{ scale }] }]}>
      <Pressable
        onPress={onPress}
        disabled={isDisabled}
        onPressIn={pressIn}
        onPressOut={pressOut}
        style={({ pressed }) => [styles.base, (pressed || isDisabled) && styles.dimmed]}
      >
        {loading
          ? <ActivityIndicator color={theme.palette.surface} />
          : <Text style={styles.label}>{text}</Text>
        }
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: '100%',
    maxWidth: theme.sizing.buttonWidth,
  },
  base: {
    width: '100%',
    height: theme.sizing.buttonHeight,
    backgroundColor: theme.palette.secondary,
    borderRadius: theme.radius.card,
    justifyContent: 'center',
    alignItems: 'center',
  },
  dimmed: { opacity: theme.opacity.hover },
  label: {
    color: theme.palette.surface,
    fontSize: theme.type.button,
    fontWeight: 'bold',
    fontFamily: theme.fontFamily,
  },
});
