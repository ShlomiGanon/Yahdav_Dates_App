import { useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chat';
import { getAccessToken } from '../auth/storage';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/axios';
import { buildWsUrl, openReconnectingSocket } from '@shared/utils/reconnectingSocket';
import type { ReconnectingSocketHandle } from '@shared/utils/reconnectingSocket';
import { CHAT_PAGE_SIZE, hasMorePages } from '@shared/utils/chatPagination';
import { createOptimisticMessage } from '@shared/utils/createOptimisticMessage';
import { classifyChatSocketFrame } from '@shared/utils/classifyChatSocketFrame';
import { clientMessage } from '@shared/copy/client';
import type { Message } from '../types/chat';

export function useMessages(peer_id: string, onStatus: (msg: string, ok: boolean) => void) {
  const { user } = useAuth();

  const socketRef         = useRef<ReconnectingSocketHandle | null>(null);
  const loadingMoreRef    = useRef(false);
  const pendingSendIdsRef = useRef<string[]>([]);

  const [messages,    setMessages]    = useState<Message[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [sending,     setSending]     = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore,     setHasMore]     = useState(true);

  useEffect(() => {
    loadHistory();
    socketRef.current = openReconnectingSocket({
      buildUrl: () => buildWsUrl(api.defaults.baseURL ?? '', getAccessToken() ?? ''),
      onMessage: (raw) => handleSocketFrame(raw),
    });
    return () => {
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  // Mirrors web's ChatMasterDetail.tsx handleSocketFrame — closes the
  // mobile/web ack-reconciliation gap noted in APP/review.md: a message
  // sent over the socket now gets its optimistic temp id swapped for the
  // server-confirmed id once the {type:"ack"} frame arrives, instead of
  // being left with the temp id forever. Frame parsing/classification
  // itself now lives in shared/utils/classifyChatSocketFrame.ts — this
  // function only owns the stateful reaction (ref bookkeeping, setState).
  function handleSocketFrame(raw: string): void
  {
      const frame = classifyChatSocketFrame(raw);

      if (frame.kind === 'ignore')
      {
          return;
      }

      if (frame.kind === 'ack')
      {
          const tempId = pendingSendIdsRef.current.shift();
          if (tempId)
          {
              const confirmedId = frame.message_id;
              setMessages((prev) => prev.map((m) => (m.message_id === tempId ? { ...m, message_id: confirmedId } : m)));
          }
          return;
      }

      const incoming = frame.message;
      if (incoming.sender_id !== user?.user_id)
      {
          setMessages((prev) => [incoming, ...prev]);
      }
  }

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
    const tempId = optimistic.message_id;
    setMessages((prev) => [optimistic, ...prev]);

    const sentOverSocket = socketRef.current?.send(
      JSON.stringify({ peer_id, content, msg_type: 'TEXT' }),
    );

    if (sentOverSocket)
    {
      // Reconciled in handleSocketFrame once the server's ack arrives.
      pendingSendIdsRef.current.push(tempId);
      return;
    }

    setSending(true);
    try {
      const data = await chatApi.sendMessage(peer_id, content, 'TEXT');
      if (!data.success) {
        setMessages((prev) =>
          prev.filter((m) => m.message_id !== tempId),
        );
        onStatus(data.message, false);
        return;
      }
      const { message_id, sender_id, msg_type, created_at } = data;
      const sent: Message = { message_id, sender_id, content: data.content, msg_type, created_at };
      setMessages((prev) =>
        prev.map((m) => (m.message_id === tempId ? sent : m)),
      );
    } catch {
      setMessages((prev) =>
        prev.filter((m) => m.message_id !== tempId),
      );
      onStatus(clientMessage('send_message_failed'), false);
    } finally {
      setSending(false);
    }
  };

  return { messages, loading, sending, loadingMore, hasMore, sendMessage, loadOlder };
}
