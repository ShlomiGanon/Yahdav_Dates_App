import { useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chat';
import { getAccessToken } from '../auth/storage';
import { api } from '../api/axios';
import { WS_RECONNECT } from '../utils/constants';
import type { Conversation } from '../types/chat';

export function useConversations() {
  const wsRef          = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef<number>(WS_RECONNECT.INITIAL_DELAY_MS);
  const reconnectCount = useRef(0);
  const unmounted      = useRef(false);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [refreshing,    setRefreshing]    = useState(false);
  const [error,         setError]         = useState('');

  useEffect(() => {
    load();
    connectWs();
    return () => {
      unmounted.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const load = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await chatApi.getConversations();
      setConversations(data);
      setError('');
    } catch {
      setError('טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const connectWs = () => {
    const token = getAccessToken();
    if (!token || unmounted.current) return;
    const wsBase = (api.defaults.baseURL ?? '').replace(/^https?/, (p) =>
      p === 'https' ? 'wss' : 'ws',
    );
    const ws = new WebSocket(`${wsBase}/ws?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
      reconnectDelay.current = WS_RECONNECT.INITIAL_DELAY_MS;
      reconnectCount.current = 0;
    };

    ws.onmessage = () => { load(); };

    ws.onclose = () => {
      if (unmounted.current) return;
      if (reconnectCount.current >= WS_RECONNECT.MAX_ATTEMPTS) return;
      reconnectTimer.current = setTimeout(() => {
        reconnectCount.current += 1;
        reconnectDelay.current = Math.min(
          reconnectDelay.current * WS_RECONNECT.BACKOFF_FACTOR,
          WS_RECONNECT.MAX_DELAY_MS,
        );
        connectWs();
      }, reconnectDelay.current);
    };

    wsRef.current = ws;
  };

  return {
    conversations,
    loading,
    refreshing,
    error,
    refresh: () => load(true),
  };
}
