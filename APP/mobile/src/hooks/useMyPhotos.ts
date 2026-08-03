import { useEffect, useState } from 'react';
import { Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { usersApi } from '../api/users';
import { resizePhoto } from '../utils/resizePhoto';
import type { Photo } from '../types/user';

export function useMyPhotos(onStatus: (msg: string, ok: boolean) => void) {
  const [photos,    setPhotos]    = useState<Photo[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const data = await usersApi.getMyPhotos();
      setPhotos(data);
    } catch {
      onStatus('שגיאה בטעינת התמונות', false);
    } finally {
      setLoading(false);
    }
  };

  const addPhoto = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      onStatus('נדרשת הרשאה לגישה לגלריה', false);
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    const uri = await resizePhoto(asset.uri, asset.width ?? 0, asset.height ?? 0);
    const form = new FormData();
    form.append('photo', { uri, name: 'photo.jpg', type: 'image/jpeg' } as any);
    setUploading(true);
    try {
      const photo = await usersApi.uploadPhoto(form);
      setPhotos((prev) => [...prev, photo]);
      onStatus('תמונה נוספה', true);
    } catch {
      onStatus('שגיאה בהעלאת התמונה', false);
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = (photo_id: string) => {
    Alert.alert(
      'מחיקת תמונה',
      'האם למחוק את התמונה?',
      [
        { text: 'ביטול', style: 'cancel' },
        {
          text: 'מחק',
          style: 'destructive',
          onPress: async () => {
            try {
              await usersApi.deletePhoto(photo_id);
              setPhotos((prev) => prev.filter((p) => p.photo_id !== photo_id));
              onStatus('תמונה הוסרה', true);
            } catch {
              onStatus('שגיאה במחיקת התמונה', false);
            }
          },
        },
      ],
    );
  };

  return { photos, loading, uploading, addPhoto, removePhoto };
}
