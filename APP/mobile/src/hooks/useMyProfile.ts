import { useEffect, useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { usersApi } from '../api/users';
import { resizePhoto } from '../utils/resizePhoto';
import type { Profile } from '../types/user';

export function useMyProfile(onStatus: (msg: string, ok: boolean) => void) {
  const [profileData, setProfileData] = useState<Profile | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [loadError,   setLoadError]   = useState('');

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const data = await usersApi.getMyProfile();
      if (!data.success) {
        setLoadError(data.message);
        return;
      }
      setProfileData(data);
    } catch {
      setLoadError('שגיאה בטעינת הפרופיל');
    } finally {
      setLoading(false);
    }
  };

  const save = async (data: Partial<Profile>) => {
    setSaving(true);
    try {
      const res = await usersApi.updateMyProfile(data);
      onStatus(res.message, res.success);
      if (res.success) {
        setProfileData(res);
      }
    } catch {
      onStatus('שגיאה בשמירת הפרופיל', false);
    } finally {
      setSaving(false);
    }
  };

  const uploadPhoto = async (): Promise<string | null> => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      onStatus('נדרשת הרשאה לגישה לגלריה', false);
      return null;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });
    if (result.canceled) return null;
    const asset = result.assets[0];
    setUploading(true);
    try {
      const uri = await resizePhoto(asset.uri, asset.width ?? 0, asset.height ?? 0);
      const form = new FormData();
      form.append('photo', { uri, name: 'photo.jpg', type: 'image/jpeg' } as any);
      const data = await usersApi.uploadMainPhoto(form);
      onStatus(data.message, data.success);
      return data.success ? data.photo_url : null;
    } catch {
      onStatus('שגיאה בהעלאת התמונה', false);
      return null;
    } finally {
      setUploading(false);
    }
  };

  return { profileData, loading, saving, uploading, loadError, save, uploadPhoto };
}
