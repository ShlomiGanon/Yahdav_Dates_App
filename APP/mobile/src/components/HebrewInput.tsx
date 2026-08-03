import React from 'react';
import { View, Text, TextInput, StyleSheet, KeyboardTypeOptions } from 'react-native';
import { theme } from '../style/theme';

type Props = {
  label?: string;
  value: string;
  onChangeText: (text: string) => void;
  isPassword?: boolean;
  multiline?: boolean;
  maxLength?: number;
  keyboardType?: KeyboardTypeOptions;
  error?: string;
  placeholder?: string;
  onSubmitEditing?: () => void;
};

export function HebrewInput({
  label, value, onChangeText, isPassword = false,
  multiline = false, maxLength, keyboardType,
  error, placeholder, onSubmitEditing,
}: Props) {
  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}
      <TextInput
        value={value}
        onChangeText={onChangeText}
        secureTextEntry={isPassword}
        multiline={multiline}
        maxLength={maxLength}
        keyboardType={keyboardType}
        placeholder={placeholder}
        placeholderTextColor={theme.palette.offline}
        onSubmitEditing={onSubmitEditing}
        textAlign="right"
        style={[styles.input, multiline && styles.multiline, !!error && styles.inputError]}
      />
      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', marginBottom: theme.spacing.sm },
  label: {
    fontSize: theme.type.small,
    color: theme.palette.textMain,
    marginBottom: theme.spacing.xs,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.palette.offline,
    borderRadius: theme.radius.card,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    fontSize: theme.type.input,
    color: theme.palette.textMain,
    backgroundColor: theme.palette.surface,
    fontFamily: theme.fontFamily,
  },
  multiline: { height: 100, textAlignVertical: 'top' },
  inputError:  { borderColor: theme.palette.danger },
  error: {
    fontSize: theme.type.small,
    color: theme.palette.danger,
    marginTop: theme.spacing.xs,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
});
