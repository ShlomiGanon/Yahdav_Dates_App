import React, { useEffect, useRef, useState } from 'react';
import {
  View, StyleSheet, SafeAreaView, ScrollView,
  KeyboardAvoidingView, Platform, Pressable, Dimensions,
} from 'react-native';
import { Image } from 'expo-image';
import { MaterialIcons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMyProfile } from '../../hooks/useMyProfile';
import { ScreenHeading } from '../../components/ScreenHeading';
import { HebrewInput } from '../../components/HebrewInput';
import { ModalPicker, PickerOption } from '../../components/ModalPicker';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { StatusBanner, StatusBannerRef } from '../../components/StatusBanner';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<MainStackParams, 'MyProfile'>;

const GENDER_OPTIONS: PickerOption[] = [
  { label: 'זכר',  value: 'male'   },
  { label: 'נקבה', value: 'female' },
  { label: 'אחר',  value: 'other'  },
];

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

const REGION_OPTIONS: PickerOption[] = [
  { label: 'מחוז הצפון',    value: 'מחוז הצפון'    },
  { label: 'מחוז חיפה',     value: 'מחוז חיפה'     },
  { label: 'מחוז המרכז',    value: 'מחוז המרכז'    },
  { label: 'מחוז תל אביב',  value: 'מחוז תל אביב'  },
  { label: 'מחוז ירושלים',  value: 'מחוז ירושלים'  },
  { label: 'מחוז הדרום',    value: 'מחוז הדרום'    },
  { label: 'יהודה ושומרון', value: 'יהודה ושומרון' },
];

const PHOTO_SIZE = 120;

export function MyProfileScreen({ navigation }: Props) {
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
    if (!name.trim())                     { setValidationError('שם מלא הוא שדה חובה');    return; }
    if (!gender)                          { setValidationError('יש לבחור מין');            return; }
    if (!dobDay || !dobMonth || !dobYear) { setValidationError('יש למלא תאריך לידה מלא'); return; }
    if (!city.trim())                     { setValidationError('עיר היא שדה חובה');        return; }

    const dobStr = `${dobYear}-${dobMonth}-${String(dobDay).padStart(2, '0')}`;
    const parsed = new Date(dobStr);
    if (isNaN(parsed.getTime()) || parsed.getDate() !== parseInt(dobDay, 10)) {
      setValidationError('תאריך לידה לא תקין');
      return;
    }
    const age = (Date.now() - parsed.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
    if (age < 18)  { setValidationError('גיל מינימלי הוא 18');  return; }
    if (age > 100) { setValidationError('גיל מקסימלי הוא 100'); return; }

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
              <Image source={{ uri: photoUrl }} style={styles.photo} contentFit="cover" />
            ) : (
              <View style={styles.photoPlaceholder}>
                <MaterialIcons name="add-a-photo" size={40} color={theme.palette.offline} />
              </View>
            )}
          </Pressable>

          <View style={styles.form}>
            {!!loadError && <ErrorCard message={loadError} />}

            <HebrewInput label="שם מלא"   value={name} onChangeText={setName} placeholder="הכנס שם מלא" />
            <ModalPicker label="מין"       options={GENDER_OPTIONS}  value={gender}    onChange={setGender}   placeholder="בחר מין"  />

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
              label="קצת עליי"
              value={bio}
              onChangeText={(t) => setBio(t.slice(0, 1000))}
              placeholder="ספר/י קצת על עצמך"
              multiline
              maxLength={1000}
            />

            {!!validationError && <ErrorCard message={validationError} />}
            <SecondaryButton text="תמונות נוספות"      onPress={() => navigation.navigate('AdditionalPhotos')} />
            <PrimaryButton   text="שמור שינויים"        onPress={validateAndSave} loading={saving} />
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
