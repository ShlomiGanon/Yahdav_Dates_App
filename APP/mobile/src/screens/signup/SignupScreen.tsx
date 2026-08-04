import React, { useState } from 'react';
import {
  View, StyleSheet, SafeAreaView,
  ScrollView, KeyboardAvoidingView, Platform,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { AUTH_FLOW_EVENTS } from '@shared/flow/authFlow';
import { deriveUsername, validatePassword, validatePasswordsMatch } from '@shared/validation/credentials';
import { clientMessage } from '@shared/copy/client';
import { useAuth } from '../../auth/AuthContext';
import { MOBILE_DESTINATIONS } from '../../navigation/destinations';
import { ScreenHeading } from '../../components/ScreenHeading';
import { HebrewInput } from '../../components/HebrewInput';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import type { AuthStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<AuthStackParams, 'Signup'>;

export function SignupScreen({ navigation }: Props) {
  const { signup } = useAuth();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const handleSignup = async () => {
    if (!email.trim() || !password || !confirm) {
      setError(clientMessage('missing_all_fields'));
      return;
    }
    if (validatePasswordsMatch(password, confirm)) {
      setError(clientMessage('passwords_dont_match'));
      return;
    }
    if (validatePassword(password)) {
      setError(clientMessage('password_too_short'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      const username = deriveUsername(email.trim());
      const result = await signup(email.trim(), username, password);
      if (!result.success) {
        setError(result.message);
        return;
      }
      // Signup no longer auto-authenticates — send the user to Login to
      // sign in with the credentials they just created.
      navigation.navigate(MOBILE_DESTINATIONS[AUTH_FLOW_EVENTS.afterSignup]);
    } catch {
      setError(clientMessage('network_error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <SafeAreaView style={styles.flex}>
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <ScreenHeading>הרשמה</ScreenHeading>
          <View style={styles.form}>
            <HebrewInput
              label="אימייל"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              placeholder="הכנס אימייל"
            />
            <HebrewInput
              label="סיסמה"
              value={password}
              onChangeText={setPassword}
              isPassword
              placeholder="לפחות 8 תווים"
            />
            <HebrewInput
              label="אימות סיסמה"
              value={confirm}
              onChangeText={setConfirm}
              isPassword
              placeholder="הכנס סיסמה שוב"
              onSubmitEditing={handleSignup}
            />
            {!!error && <ErrorCard message={error} />}
            <PrimaryButton   text="הירשם"                    onPress={handleSignup}                    loading={loading} />
            <SecondaryButton text="יש לך חשבון? התחברות" onPress={() => navigation.navigate('Login')} />
          </View>
        </ScrollView>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.lg,
    gap: theme.spacing.lg,
  },
  form: {
    width: '100%',
    alignItems: 'center',
    gap: theme.spacing.md,
  },
});
