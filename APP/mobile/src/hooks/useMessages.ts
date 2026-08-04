import { useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chat';
import { getAccessToken } from '../auth/storage';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/axios';
import { WS_RECONNECT } from '../utils/constants';
import type { Message } from '../types/chat';

const PAGE_SIZE = 20;

export function useMessages(peer_id: string, onStatus: (msg: string, ok: boolean) => void) {
  const { user } = useAuth();

  const wsRef          = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef<number>(WS_RECONNECT.INITIAL_DELAY_MS);
  const reconnectCount = useRef(0);
  const unmounted      = useRef(false);
  const loadingMoreRef = useRef(false);

  const [messages,    setMessages]    = useState<Message[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [sending,     setSending]     = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore,     setHasMore]     = useState(true);

  useEffect(() => {
    loadHistory();
    connectWs();
    return () => {
      unmounted.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const loadHistory = async () => {
    try {
      const data = await chatApi.getMessages(peer_id, { limit: PAGE_SIZE });
      if (!data.success) {
        onStatus(data.message, false);
        return;
      }
      setMessages([...data.messages].reverse());
      setHasMore(data.messages.length === PAGE_SIZE);
      chatApi.markRead(peer_id).catch(() => {});
    } catch {
      onStatus('טעינת השיחה נכשלה. אנא נסה/י שוב.', false);
    } finally {
      setLoading(false);
    }
  };

  const loadOlder = async () => {
    const oldest = messages[messages.length - 1];
    if (loadingMoreRef.current || !hasMore || !oldest) return;

    loadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      const data = await chatApi.getMessages(peer_id, {
        before: oldest.message_id,
        limit: PAGE_SIZE,
      });
      if (!data.success) {
        onStatus(data.message, false);
        return;
      }
      setMessages((cur) => [...cur, ...[...data.messages].reverse()]);
      setHasMore(data.messages.length === PAGE_SIZE);
    } catch {
      onStatus('שגיאה בטעינת הודעות ישנות', false);
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
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

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as Message & { type?: string };
        if (msg.sender_id && msg.sender_id !== user?.user_id) {
          setMessages((prev) => [msg, ...prev]);
        }
      } catch {}
    };

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

  const sendMessage = async (content: string) => {
    if (!content || sending) return;

    const optimistic: Message = {
      message_id: `tmp-${Date.now()}`,
      sender_id:  user?.user_id ?? '',
      content,
      msg_type:   'TEXT',
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [optimistic, ...prev]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ peer_id, content, msg_type: 'TEXT' }));
    } else {
      setSending(true);
      try {
        const data = await chatApi.sendMessage(peer_id, content, 'TEXT');
        if (!data.success) {
          setMessages((prev) =>
            prev.filter((m) => m.message_id !== optimistic.message_id),
          );
          onStatus(data.message, false);
          return;
        }
        const { message_id, sender_id, msg_type, created_at } = data;
        const sent: Message = { message_id, sender_id, content: data.content, msg_type, created_at };
        setMessages((prev) =>
          prev.map((m) => (m.message_id === optimistic.message_id ? sent : m)),
        );
      } catch {
        setMessages((prev) =>
          prev.filter((m) => m.message_id !== optimistic.message_id),
        );
        onStatus('שליחת ההודעה נכשלה. נסה/י שנית.', false);
      } finally {
        setSending(false);
      }
    }
  };

  return { messages, loading, sending, loadingMore, hasMore, sendMessage, loadOlder };
}
