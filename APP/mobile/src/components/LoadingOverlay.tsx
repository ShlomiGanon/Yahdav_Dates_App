import React from 'react';
import { Modal, View, ActivityIndicator, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

type Props = { visible: boolean };

export function LoadingOverlay({ visible }: Props) {
  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.overlay}>
        <ActivityIndicator size="large" color={theme.palette.primary} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: `rgba(0,0,0,${theme.opacity.formOverlay})`,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
