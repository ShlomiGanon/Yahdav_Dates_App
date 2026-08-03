import React, { useState } from 'react';
import { View, Text, Modal, Pressable, FlatList, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

export type PickerOption = { label: string; value: string };

type Props = {
  label?: string;
  options: PickerOption[];
  value: string | null;
  onChange: (value: string) => void;
  placeholder?: string;
};

export function ModalPicker({ label, options, value, onChange, placeholder = 'בחר...' }: Props) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);

  const handleSelect = (val: string) => {
    onChange(val);
    setOpen(false);
  };

  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}

      <Pressable
        onPress={() => setOpen(true)}
        style={({ pressed }) => [styles.trigger, pressed && styles.pressed]}
      >
        <Text style={[styles.triggerText, !selected && styles.placeholder]}>
          {selected ? selected.label : placeholder}
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)} />
        <View style={styles.sheet}>
          {label && <Text style={styles.sheetTitle}>{label}</Text>}
          <FlatList
            data={options}
            keyExtractor={(item) => item.value}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => handleSelect(item.value)}
                style={({ pressed }) => [styles.option, pressed && styles.pressed]}
              >
                <Text style={[styles.optionText, item.value === value && styles.selectedText]}>
                  {item.label}
                </Text>
              </Pressable>
            )}
          />
        </View>
      </Modal>
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
  trigger: {
    borderWidth: 1,
    borderColor: theme.palette.offline,
    borderRadius: theme.radius.card,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm + 2,
    backgroundColor: theme.palette.surface,
  },
  triggerText: {
    fontSize: theme.type.input,
    color: theme.palette.textMain,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  placeholder: { color: theme.palette.offline },
  pressed:     { opacity: theme.opacity.hover },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  sheet: {
    backgroundColor: theme.palette.surface,
    borderTopLeftRadius: theme.radius.card,
    borderTopRightRadius: theme.radius.card,
    maxHeight: '60%',
    paddingBottom: theme.spacing.lg,
  },
  sheetTitle: {
    fontSize: theme.type.h2,
    fontWeight: 'bold',
    color: theme.palette.textMain,
    textAlign: 'center',
    padding: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.palette.offline,
    fontFamily: theme.fontFamily,
  },
  option: {
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.palette.offline,
  },
  optionText: {
    fontSize: theme.type.body,
    color: theme.palette.textMain,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  selectedText: { color: theme.palette.primary, fontWeight: 'bold' },
});
