import { useEffect, useState } from 'react';
import { usersApi } from '../api/users';

export function usePeerPhotos(peer_id: string) {
  const [photos,    setPhotos]    = useState<Array<{ url: string }>>([]);
  const [peerName,  setPeerName]  = useState('');
  const [loading,   setLoading]   = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const data = await usersApi.getPeerPhotos(peer_id);
      if (!data.success) {
        setLoadError(data.message);
        return;
      }
      setPeerName(data.name ?? '');
      setPhotos(data.photos ?? []);
    } catch {
      setLoadError('משהו השתבש בטעינת התמונות');
    } finally {
      setLoading(false);
    }
  };

  return { photos, peerName, loading, loadError };
}
