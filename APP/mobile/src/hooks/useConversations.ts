import { useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chat';
import { getAccessToken } from '../auth/storage';
import { api } from '../api/axios';
import { buildWsUrl, openReconnectingSocket } from '@shared/utils/reconnectingSocket';
import type { ReconnectingSocketHandle } from '@shared/utils/reconnectingSocket';
import type { Conversation } from '../types/chat';

export function useConversations() {
  const socketRef = useRef<ReconnectingSocketHandle | null>(null);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [refreshing,    setRefreshing]    = useState(false);
  const [error,         setError]         = useState('');

  useEffect(() => {
    load();
    socketRef.current = openReconnectingSocket({
      buildUrl: () => buildWsUrl(api.defaults.baseURL ?? '', getAccessToken() ?? ''),
      onMessage: () => { load(); },
    });
    return () => {
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const load = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await chatApi.getConversations();
      if (!data.success) {
        setError(data.message);
        return;
      }
      setConversations(data.conversations);
      setError('');
    } catch {
      setError('טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  return {
    conversations,
    loading,
    refreshing,
    error,
    refresh: () => load(true),
  };
}
