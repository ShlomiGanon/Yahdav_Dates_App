import { useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chat';
import { getAccessToken } from '../auth/storage';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/axios';
import { buildWsUrl, openReconnectingSocket } from '@shared/utils/reconnectingSocket';
import type { ReconnectingSocketHandle } from '@shared/utils/reconnectingSocket';
import { CHAT_PAGE_SIZE, hasMorePages } from '@shared/utils/chatPagination';
import { createOptimisticMessage } from '@shared/utils/createOptimisticMessage';
import { clientMessage } from '@shared/copy/client';
import type { Message } from '../types/chat';

export function useMessages(peer_id: string, onStatus: (msg: string, ok: boolean) => void) {
  const { user } = useAuth();

  const socketRef      = useRef<ReconnectingSocketHandle | null>(null);
  const loadingMoreRef = useRef(false);

  const [messages,    setMessages]    = useState<Message[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [sending,     setSending]     = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore,     setHasMore]     = useState(true);

  useEffect(() => {
    loadHistory();
    socketRef.current = openReconnectingSocket({
      buildUrl: () => buildWsUrl(api.defaults.baseURL ?? '', getAccessToken() ?? ''),
      onMessage: (raw) => {
        try {
          const msg = JSON.parse(raw) as Message & { type?: string };
          if (msg.sender_id && msg.sender_id !== user?.user_id) {
            setMessages((prev) => [msg, ...prev]);
          }
        } catch {}
      },
    });
    return () => {
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const loadHistory = async () => {
    try {
      const data = await chatApi.getMessages(peer_id, { limit: CHAT_PAGE_SIZE });
      if (!data.success) {
        onStatus(data.message, false);
        return;
      }
      setMessages([...data.messages].reverse());
      setHasMore(hasMorePages(data.messages.length));
      chatApi.markRead(peer_id).catch(() => {});
    } catch {
      onStatus(clientMessage('load_messages_failed'), false);
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
        limit: CHAT_PAGE_SIZE,
      });
      if (!data.success) {
        onStatus(data.message, false);
        return;
      }
      setMessages((cur) => [...cur, ...[...data.messages].reverse()]);
      setHasMore(hasMorePages(data.messages.length));
    } catch {
      onStatus(clientMessage('load_older_messages_failed'), false);
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  };

  const sendMessage = async (content: string) => {
    if (!content || sending) return;

    const optimistic = createOptimisticMessage(content, user?.user_id ?? '');
    setMessages((prev) => [optimistic, ...prev]);

    const sentOverSocket = socketRef.current?.send(
      JSON.stringify({ peer_id, content, msg_type: 'TEXT' }),
    );

    if (!sentOverSocket) {
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
        onStatus(clientMessage('send_message_failed'), false);
      } finally {
        setSending(false);
      }
    }
  };

  return { messages, loading, sending, loadingMore, hasMore, sendMessage, loadOlder };
}
