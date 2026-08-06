import { useEffect, useState } from 'react';
import { Alert } from 'react-native';
import { usersApi } from '../api/users';
import { blockPeer } from '@shared/utils/blockPeer';
import { clientMessage } from '@shared/copy/client';
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
      if (!data.success) {
        setLoadError(data.message);
        return;
      }
      setProfile(data);
    } catch {
      setLoadError(clientMessage('load_peer_profile_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleBlock = async () => {
    setBlocking(true);
    try {
      await blockPeer(usersApi.blockUser, peer_id, {
        onSuccess: onBlocked,
        onError: (message) => Alert.alert('שגיאה', message),
      });
    } finally {
      setBlocking(false);
    }
  };

  const confirmBlock = () => {
    Alert.alert(
      'חסימת משתמש',
      `האם לחסום את ${profile?.name || clientMessage('unknown_user_label')}?`,
      [
        { text: 'ביטול', style: 'cancel' },
        { text: 'חסום משתמש', style: 'destructive', onPress: handleBlock },
      ],
    );
  };

  return { profile, loading, blocking, loadError, confirmBlock };
}
