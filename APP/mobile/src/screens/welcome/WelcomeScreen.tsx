import React from 'react';
import { View, StyleSheet, SafeAreaView } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenHeading } from '../../components/ScreenHeading';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import type { AuthStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<AuthStackParams, 'Welcome'>;

export function WelcomeScreen({ navigation }: Props) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <ScreenHeading>יחדיו</ScreenHeading>
        <View style={styles.buttons}>
          <PrimaryButton   text="התחברות" onPress={() => navigation.navigate('Login')}  />
          <SecondaryButton text="הרשמה"   onPress={() => navigation.navigate('Signup')} />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.lg,
    gap: theme.spacing.lg,
  },
  buttons: {
    width: '100%',
    alignItems: 'center',
    gap: theme.spacing.md,
  },
});
