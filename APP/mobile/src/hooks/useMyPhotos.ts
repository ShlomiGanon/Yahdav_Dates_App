import { useEffect, useState } from 'react';
import { Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { usersApi } from '../api/users';
import { resizePhoto } from '../utils/resizePhoto';
import { clientMessage } from '@shared/copy/client';
import type { Photo } from '../types/user';

export function useMyPhotos(onStatus: (msg: string, ok: boolean) => void) {
  const [photos,    setPhotos]    = useState<Photo[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const data = await usersApi.getMyPhotos();
      if (!data.success) {
        onStatus(data.message, false);
        return;
      }
      setPhotos(data.photos);
    } catch {
      onStatus(clientMessage('load_photos_failed'), false);
    } finally {
      setLoading(false);
    }
  };

  const addPhoto = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      onStatus(clientMessage('gallery_permission_required'), false);
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    setUploading(true);
    try {
      const uri = await resizePhoto(asset.uri, asset.width ?? 0, asset.height ?? 0);
      const form = new FormData();
      form.append('photo', { uri, name: 'photo.jpg', type: 'image/jpeg' } as any);
      const data = await usersApi.uploadPhoto(form);
      if (data.success) {
        setPhotos((prev) => [...prev, data]);
      }
      onStatus(data.message, data.success);
    } catch {
      onStatus(clientMessage('upload_photo_failed'), false);
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = (photo_id: string) => {
    Alert.alert(
      'מחיקת תמונה',
      clientMessage('confirm_delete_photo_message'),
      [
        { text: 'ביטול', style: 'cancel' },
        {
          text: 'מחק',
          style: 'destructive',
          onPress: async () => {
            try {
              const data = await usersApi.deletePhoto(photo_id);
              if (data.success) {
                setPhotos((prev) => prev.filter((p) => p.photo_id !== photo_id));
              }
              onStatus(data.message, data.success);
            } catch {
              onStatus(clientMessage('delete_photo_failed'), false);
            }
          },
        },
      ],
    );
  };

  return { photos, loading, uploading, addPhoto, removePhoto };
}
