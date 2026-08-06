import React, { useEffect, useRef, useState } from 'react';
import {
  View, StyleSheet, SafeAreaView, ScrollView,
  KeyboardAvoidingView, Platform, Pressable, Dimensions,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { validateProfileForm } from '@shared/validation/profile';
import { clientMessage } from '@shared/copy/client';
import { useMyProfile } from '../../hooks/useMyProfile';
import { ScreenHeading } from '../../components/ScreenHeading';
import { HebrewInput } from '../../components/HebrewInput';
import { ModalPicker, PickerOption } from '../../components/ModalPicker';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { StatusBanner, StatusBannerRef } from '../../components/StatusBanner';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import { RemoteImage } from '../../components/RemoteImage';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';
import { GENDER_OPTIONS } from '@shared/reference/genderOptions';
import { REGION_OPTIONS } from '@shared/reference/regionOptions';

type Props = NativeStackScreenProps<MainStackParams, 'Profile'>;

const DAY_OPTIONS: PickerOption[] = Array.from({ length: 31 }, (_, i) => ({
  label: String(i + 1),
  value: String(i + 1),
}));

const MONTH_OPTIONS: PickerOption[] = Array.from({ length: 12 }, (_, i) => ({
  label: String(i + 1).padStart(2, '0'),
  value: String(i + 1).padStart(2, '0'),
}));

const THIS_YEAR = new Date().getFullYear();
const YEAR_OPTIONS: PickerOption[] = Array.from(
  { length: THIS_YEAR - 18 - (THIS_YEAR - 100) + 1 },
  (_, i) => {
    const year = THIS_YEAR - 18 - i;
    return { label: String(year), value: String(year) };
  },
);

const PHOTO_SIZE = 120;

export function ProfileScreen({ navigation }: Props) {
  const bannerRef = useRef<StatusBannerRef>(null);

  const { profileData, loading, saving, uploading, loadError, save, uploadPhoto } =
    useMyProfile((msg, ok) => bannerRef.current?.showStatus(msg, ok));

  const [name,       setName]       = useState('');
  const [bio,        setBio]        = useState('');
  const [gender,     setGender]     = useState<string | null>(null);
  const [dobDay,     setDobDay]     = useState<string | null>(null);
  const [dobMonth,   setDobMonth]   = useState<string | null>(null);
  const [dobYear,    setDobYear]    = useState<string | null>(null);
  const [city,       setCity]       = useState('');
  const [region,     setRegion]     = useState<string | null>(null);
  const [photoUrl,   setPhotoUrl]   = useState<string | null>(null);
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    if (!profileData) return;
    setName(profileData.name ?? '');
    setBio(profileData.bio ?? '');
    setGender(profileData.gender ?? null);
    setCity(profileData.city ?? '');
    setRegion(profileData.region ?? null);
    setPhotoUrl(profileData.photo_url ?? null);
    if (profileData.date_of_birth) {
      const [y, m, d] = profileData.date_of_birth.split('-');
      setDobYear(y ?? null);
      setDobMonth(m ?? null);
      setDobDay(d ? String(parseInt(d, 10)) : null);
    }
  }, [profileData]);

  const handlePickPhoto = async () => {
    const newUrl = await uploadPhoto();
    if (newUrl) setPhotoUrl(newUrl);
  };

  const validateAndSave = async () => {
    setValidationError('');

    // Mobile only has a fully-specified date once all three pickers are
    // set — an incomplete date collapses to '' so validateProfileForm's
    // date_of_birth_required branch fires, same as before this extraction.
    const dobStr = dobDay && dobMonth && dobYear
      ? `${dobYear}-${dobMonth}-${String(dobDay).padStart(2, '0')}`
      : '';

    const formError = validateProfileForm({ name, gender, date_of_birth: dobStr, city });
    if (formError) { setValidationError(clientMessage(formError)); return; }

    await save({
      name:          name.trim(),
      bio:           bio.trim(),
      gender,
      date_of_birth: dobStr,
      city:          city.trim(),
      region:        region ?? '',
    });
  };

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <SafeAreaView style={styles.flex}>
        <LoadingOverlay visible={loading || uploading} />
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <ScreenHeading>הפרופיל שלי</ScreenHeading>
          <StatusBanner ref={bannerRef} />

          <Pressable onPress={handlePickPhoto} style={styles.photoPressable}>
            {photoUrl ? (
              <RemoteImage uri={photoUrl} style={styles.photo} contentFit="cover" />
            ) : (
              <View style={styles.photoPlaceholder}>
                <MaterialIcons name="add-a-photo" size={40} color={theme.palette.offline} />
              </View>
            )}
          </Pressable>

          <View style={styles.form}>
            {!!loadError && <ErrorCard message={loadError} />}

            <HebrewInput label="שם מלא"   value={name} onChangeText={setName} placeholder="הכנס שם מלא" />
            <ModalPicker label={clientMessage('gender_label')} options={GENDER_OPTIONS}  value={gender}    onChange={setGender}   placeholder="בחר מין"  />

            <View style={styles.dobRow}>
              <View style={styles.dobCell}>
                <ModalPicker label="יום"   options={DAY_OPTIONS}   value={dobDay}   onChange={setDobDay}   placeholder="יום"   />
              </View>
              <View style={styles.dobCell}>
                <ModalPicker label="חודש"  options={MONTH_OPTIONS} value={dobMonth} onChange={setDobMonth} placeholder="חודש"  />
              </View>
              <View style={styles.dobCell}>
                <ModalPicker label="שנה"   options={YEAR_OPTIONS}  value={dobYear}  onChange={setDobYear}  placeholder="שנה"  />
              </View>
            </View>

            <HebrewInput label="עיר"     value={city} onChangeText={setCity} placeholder="הכנס עיר" />
            <ModalPicker label="אזור"    options={REGION_OPTIONS} value={region} onChange={setRegion} placeholder="בחר אזור" />
            <HebrewInput
              label={clientMessage('about_me_label')}
              value={bio}
              onChangeText={(t) => setBio(t.slice(0, 1000))}
              placeholder="ספר/י קצת על עצמך"
              multiline
              maxLength={1000}
            />

            {!!validationError && <ErrorCard message={validationError} />}
            <SecondaryButton text={clientMessage('additional_photos_label')} onPress={() => navigation.navigate('AdditionalPhotos')} />
            <PrimaryButton   text={clientMessage('save_changes_label')}      onPress={validateAndSave} loading={saving} />
            <SecondaryButton text="חזור לתפריט הראשי"  onPress={() => navigation.navigate('Menu')} />
          </View>
        </ScrollView>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex:      { flex: 1 },
  container: {
    flexGrow: 1,
    alignItems: 'center',
    padding: theme.spacing.lg,
    gap: theme.spacing.lg,
  },
  photoPressable: {
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
    borderWidth: 2,
    borderColor: theme.palette.offline,
    borderStyle: 'dashed',
  },
  form: {
    width: '100%',
    alignItems: 'center',
    gap: theme.spacing.md,
  },
  dobRow: {
    flexDirection: 'row',
    width: '100%',
    gap: theme.spacing.sm,
  },
  dobCell: { flex: 1 },
});
