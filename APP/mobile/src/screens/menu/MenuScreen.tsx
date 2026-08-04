import React from 'react';
import { View, StyleSheet, SafeAreaView } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useAuth } from '../../auth/AuthContext';
import { ScreenHeading } from '../../components/ScreenHeading';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { Divider } from '../../components/Divider';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<MainStackParams, 'Menu'>;

export function MenuScreen({ navigation }: Props) {
  const { logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <ScreenHeading>תפריט ראשי</ScreenHeading>
        <View style={styles.buttons}>
          <PrimaryButton text="עריכת הפרופיל שלי"    onPress={() => navigation.navigate('Profile')}     />
          <PrimaryButton text="צפייה במשתמשים אחרים" onPress={() => navigation.navigate('Discover')}    />
          <PrimaryButton text="היסטוריית שיחות"       onPress={() => navigation.navigate('ChatHistory')} />
        </View>
        <Divider />
        <SecondaryButton text="התנתק מהמערכת" onPress={logout} />
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
