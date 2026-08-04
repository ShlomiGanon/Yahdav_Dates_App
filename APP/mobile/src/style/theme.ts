import { colors } from '@shared/theme/colors';

export const theme = {
  // System default font. To swap: set to a loaded font name + add expo-font loading in main.tsx.
  fontFamily: undefined as string | undefined,

  palette: colors,
  type: {
    h1: 50, h2: 28, heading: 24, button: 22, body: 16, input: 20, small: 14, caption: 12,
  },
  sizing: {
    buttonWidth: 400, buttonHeight: 70,
    avatarSm: 40, avatarLg: 80,
    iconLg: 32,
  },
  spacing: {
    none: 0, xs: 4, sm: 8, md: 14, lg: 24,
  },
  radius: {
    card: 16, bubble: 18,
  },
  motion: {
    animMs: 240,
  },
  opacity: {
    formOverlay: 0.85, hover: 0.8,
  },
} as const;
