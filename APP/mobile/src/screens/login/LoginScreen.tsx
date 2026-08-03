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

type Props = NativeStackScreenProps<AuthStackParams, 'Login'>;

export function LoginScreen({ navigation }: Props) {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password,   setPassword]   = useState('');
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState('');

  const handleLogin = async () => {
    if (!identifier.trim() || !password) {
      setError('יש למלא את כל השדות');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(identifier.trim(), password);
      // RootNavigator auto-switches to MainStack when user state is set
    } catch {
      setError('שם משתמש או סיסמה שגויים');
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
          <ScreenHeading>התחברות</ScreenHeading>
          <View style={styles.form}>
            <HebrewInput
              label="אימייל / שם משתמש"
              value={identifier}
              onChangeText={setIdentifier}
              keyboardType="email-address"
              placeholder="הכנס אימייל או שם משתמש"
            />
            <HebrewInput
              label="סיסמה"
              value={password}
              onChangeText={setPassword}
              isPassword
              placeholder="הכנס סיסמה"
              onSubmitEditing={handleLogin}
            />
            {!!error && <ErrorCard message={error} />}
            <PrimaryButton   text="התחבר"              onPress={handleLogin}                      loading={loading} />
            <SecondaryButton text="אין לך חשבון? הרשמה" onPress={() => navigation.navigate('Signup')} />
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
