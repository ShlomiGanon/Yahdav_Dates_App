import { useEffect, useState } from 'react';
import { Alert } from 'react-native';
import { usersApi } from '../api/users';
import type { PeerProfile } from '../types/user';

export function usePeerProfile(peer_id: string, onBlocked: () => void) {
  const [profile,   setProfile]   = useState<PeerProfile | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [blocking,  setBlocking]  = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const data = await usersApi.getPeerProfile(peer_id);
      setProfile(data);
    } catch {
      setLoadError('משהו השתבש בטעינת הפרופיל');
    } finally {
      setLoading(false);
    }
  };

  const handleBlock = async () => {
    setBlocking(true);
    try {
      await usersApi.blockUser(peer_id);
      onBlocked();
    } catch {
      Alert.alert('שגיאה', 'החסימה נכשלה. נסה/י שנית.');
    } finally {
      setBlocking(false);
    }
  };

  const confirmBlock = () => {
    Alert.alert(
      'חסימת משתמש',
      `האם לחסום את ${profile?.name || 'משתמש/ת'}?`,
      [
        { text: 'ביטול', style: 'cancel' },
        { text: 'חסום משתמש', style: 'destructive', onPress: handleBlock },
      ],
    );
  };

  return { profile, loading, blocking, loadError, confirmBlock };
}
