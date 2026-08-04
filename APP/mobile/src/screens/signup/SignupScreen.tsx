import React, { useState } from 'react';
import {
  View, StyleSheet, SafeAreaView,
  ScrollView, KeyboardAvoidingView, Platform,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useAuth } from '../../auth/AuthContext';
import { ScreenHeading } from '../../components/ScreenHeading';
import { HebrewInput } from '../../components/HebrewInput';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import type { AuthStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<AuthStackParams, 'Signup'>;

// Derive a username from the email local-part (strip domain, sanitize)
function deriveUsername(email: string): string {
  return (email.split('@')[0] ?? '')
    .replace(/[^a-zA-Z0-9_]/g, '')
    .toLowerCase()
    .slice(0, 30);
}

export function SignupScreen({ navigation }: Props) {
  const { signup } = useAuth();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const handleSignup = async () => {
    if (!email.trim() || !password || !confirm) {
      setError('יש למלא את כל השדות');
      return;
    }
    if (password !== confirm) {
      setError('הסיסמאות אינן תואמות');
      return;
    }
    if (password.length < 8) {
      setError('הסיסמה חייבת להכיל לפחות 8 תווים');
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
      navigation.navigate('Login');
    } catch {
      setError('שגיאת רשת, נסה שנית');
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
