import React from 'react';
import {
  View, Text, StyleSheet, SafeAreaView, ScrollView, Pressable,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { usePeerProfile } from '../../hooks/usePeerProfile';
import { ScreenHeading } from '../../components/ScreenHeading';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import { RemoteImage } from '../../components/RemoteImage';
import type { MainStackParams } from '../../types/navigation';
import type { PeerProfile } from '../../types/user';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<MainStackParams, 'PeerProfile'>;

const PHOTO_SIZE = 120;

function genderLabel(g: string | null): string | null {
  if (g === 'male')   return 'זכר';
  if (g === 'female') return 'נקבה';
  if (g === 'other')  return 'אחר';
  return null;
}

function calcAge(dob: string | null): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime()) || d.getFullYear() <= 1900) return null;
  return Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000));
}

function formatDob(dob: string | null): string | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime()) || d.getFullYear() <= 1900) return null;
  return `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;
}

export function PeerProfileScreen({ route, navigation }: Props) {
  const { peer_id } = route.params;

  const { profile, loading, blocking, loadError, confirmBlock } = usePeerProfile(
    peer_id,
    () => navigation.navigate('Discover'),
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <LoadingOverlay visible />
      </SafeAreaView>
    );
  }

  if (loadError || !profile) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.errorContainer}>
          <ErrorCard message={loadError || 'הפרופיל לא נמצא.'} />
          <SecondaryButton text="חזור" onPress={() => navigation.goBack()} />
        </View>
      </SafeAreaView>
    );
  }

  const age      = calcAge(profile.date_of_birth);
  const dob      = formatDob(profile.date_of_birth);
  const gender   = genderLabel(profile.gender);
  const location = [profile.city, profile.region].filter(Boolean).join(', ');

  return (
    <SafeAreaView style={styles.safe}>
      <LoadingOverlay visible={blocking} />

      <View style={styles.headerRow}>
        <Pressable onPress={confirmBlock} hitSlop={8} style={styles.menuBtn}>
          <MaterialIcons name="more-horiz" size={28} color={theme.palette.textMain} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.photoWrap}>
          {profile.photo_url ? (
            <RemoteImage uri={profile.photo_url} style={styles.photo} contentFit="cover" />
          ) : (
            <View style={styles.photoPlaceholder}>
              <MaterialIcons name="person" size={60} color={theme.palette.offline} />
            </View>
          )}
        </View>

        <ScreenHeading>{profile.name || 'משתמש/ת'}</ScreenHeading>

        <View style={styles.fields}>
          {gender     && <FieldRow label="מין"          value={gender} />}
          {age !== null && <FieldRow label="גיל"         value={String(age)} />}
          {dob        && <FieldRow label="תאריך לידה"   value={dob} />}
          {location   && <FieldRow label="מיקום"         value={location} />}
          {!!profile.bio && <FieldRow label="קצת עליי"  value={profile.bio} multiline />}
          {!gender && age === null && !location && !profile.bio && (
            <FieldRow label="פרטים נוספים" value="המשתמש/ת עדיין לא השלים/ה את הפרופיל." />
          )}
        </View>

        {profile.has_extra_photos && (
          <PrimaryButton
            text="להצגת תמונות נוספות"
            onPress={() => navigation.navigate('PeerPhotos', { peer_id })}
          />
        )}
        <SecondaryButton text="חזור" onPress={() => navigation.navigate('Discover')} />
      </ScrollView>
    </SafeAreaView>
  );
}

function FieldRow({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) {
  return (
    <View style={fieldStyles.row}>
      <Text style={fieldStyles.label}>{label}</Text>
      <Text style={[fieldStyles.value, multiline && fieldStyles.multilineValue]}>{value}</Text>
    </View>
  );
}

const fieldStyles = StyleSheet.create({
  row: {
    width: '100%',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.palette.offline,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.xs,
  },
  label: {
    fontSize: theme.type.small,
    color: theme.palette.offline,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  value: {
    fontSize: theme.type.body,
    color: theme.palette.textMain,
    textAlign: 'right',
    fontFamily: theme.fontFamily,
  },
  multilineValue: { lineHeight: theme.type.body * 1.5 },
});

const styles = StyleSheet.create({
  safe:      { flex: 1 },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    paddingHorizontal: theme.spacing.md,
    paddingTop: theme.spacing.sm,
  },
  menuBtn:   { padding: theme.spacing.xs },
  container: { alignItems: 'center', padding: theme.spacing.lg, gap: theme.spacing.lg },
  photoWrap: {
    width: PHOTO_SIZE,
    height: PHOTO_SIZE,
    borderRadius: PHOTO_SIZE / 2,
    overflow: 'hidden',
  },
  photo: { width: PHOTO_SIZE, height: PHOTO_SIZE },
  photoPlaceholder: {
    width: PHOTO_SIZE,
    height: PHOTO_SIZE,
    backgroundColor: theme.palette.surface,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: PHOTO_SIZE / 2,
  },
  fields:         { width: '100%', gap: theme.spacing.xs },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.lg,
    gap: theme.spacing.lg,
  },
});
