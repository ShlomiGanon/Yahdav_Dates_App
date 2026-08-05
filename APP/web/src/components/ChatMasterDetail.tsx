import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { buildWsUrl, openReconnectingSocket } from '@shared/utils/reconnectingSocket';
import type { ReconnectingSocketHandle } from '@shared/utils/reconnectingSocket';
import { formatConversationTime } from '@shared/utils/formatDate';
import type { Conversation, Message } from '@shared/types/chat';
import { AppShell } from './AppShell';
import { ChatBubble } from './ChatBubble';
import { chatApi, usersApi, axiosClient } from '../api/client';
import { webTokenStorage } from '../auth/storage';
import { useAuth } from '../auth/AuthContext';
import { PAGE_ROUTES } from '../pages/routes';

const PAGE_SIZE = 20;
const PREVIEW_MAX = 38;

function buildPreview(conv: Conversation, selfId: string): string
{
    let body: string;

    if (conv.last_msg_type === 'AUDIO')
    {
        body = '🎤 הודעה קולית';
    }
    else if (conv.last_msg_type === 'IMAGE')
    {
        body = '📷 תמונה';
    }
    else
    {
        body = (conv.last_content || '').trim();
        if (body.length > PREVIEW_MAX)
        {
            body = body.slice(0, PREVIEW_MAX) + '…';
        }
    }

    const prefix = conv.last_sender_id === selfId ? 'את/ה: ' : '';
    return prefix + body;
}

// Desktop's master-detail chat: mobile's ChatHistoryScreen (conversation
// list) and ChatScreen (one conversation) live as separate stack screens
// because a phone only has room for one at a time. On a wide viewport
// there's no reason to make that same trade — both PageIds (chatHistory,
// chat) render this same split view, just with a different right-hand
// pane. One WebSocket per mount feeds both halves instead of each screen
// opening its own, since here they're mounted together.
export function ChatMasterDetail()
{
    const { peer_id } = useParams<{ peer_id: string }>();
    const navigate     = useNavigate();
    const { user }     = useAuth();

    const socketRef         = useRef<ReconnectingSocketHandle | null>(null);
    const peerIdRef         = useRef<string | undefined>(peer_id);
    const pendingSendIdsRef = useRef<string[]>([]);
    const messageListRef    = useRef<HTMLDivElement | null>(null);
    const olderScrollHeightRef = useRef<number | null>(null);
    const conversationsRef  = useRef<Conversation[]>([]);

    const [conversations,       setConversations]       = useState<Conversation[]>([]);
    const [conversationsLoading, setConversationsLoading] = useState(true);
    const [conversationsError,  setConversationsError]  = useState('');

    const [peerName,     setPeerName]     = useState('');
    const [messages,     setMessages]     = useState<Message[]>([]);
    const [messagesLoading, setMessagesLoading] = useState(false);
    const [messagesError,   setMessagesError]   = useState('');
    const [loadingOlder,    setLoadingOlder]    = useState(false);
    const [hasOlder,        setHasOlder]        = useState(true);
    const [composerText,    setComposerText]    = useState('');
    const [sending,         setSending]         = useState(false);

    // ── Conversation list + the single live socket ──────────────────────
    useEffect(() =>
    {
        loadConversations(true);

        socketRef.current = openReconnectingSocket({
            buildUrl: () => buildWsUrl(axiosClient.defaults.baseURL ?? '', webTokenStorage.getAccessToken() ?? ''),
            onMessage: (raw) => handleSocketFrame(raw),
        });

        return () =>
        {
            socketRef.current?.close();
            socketRef.current = null;
        };
    }, []);

    function handleSocketFrame(raw: string): void
    {
        let frame: (Message & { type?: string }) | { type: string; message_id?: string };

        try
        {
            frame = JSON.parse(raw);
        }
        catch
        {
            return;
        }

        if (frame.type === 'ack' && 'message_id' in frame && frame.message_id)
        {
            const tempId = pendingSendIdsRef.current.shift();
            if (tempId)
            {
                const confirmedId = frame.message_id;
                setMessages((prev) => prev.map((m) => (m.message_id === tempId ? { ...m, message_id: confirmedId } : m)));
            }
            return;
        }

        if (frame.type === 'error' || frame.type === 'pong')
        {
            return;
        }

        const incoming = frame as Message;
        if (!incoming.sender_id || incoming.content === undefined)
        {
            return;
        }

        loadConversations(false);

        if (incoming.sender_id === peerIdRef.current)
        {
            setMessages((prev) => [...prev, incoming]);
            chatApi.markRead(incoming.sender_id).catch(() => {});
            requestAnimationFrame(scrollToBottom);
        }
    }

    // ── Selected conversation ────────────────────────────────────────────
    useEffect(() =>
    {
        peerIdRef.current = peer_id;
        setMessages([]);
        setMessagesError('');
        setHasOlder(true);

        if (peer_id)
        {
            loadPeerName(peer_id);
            loadMessages(peer_id);
        }
        else
        {
            setPeerName('');
        }
    }, [peer_id]);

    async function loadConversations(showSpinner: boolean): Promise<void>
    {
        if (showSpinner)
        {
            setConversationsLoading(true);
        }

        try
        {
            const data = await chatApi.getConversations();
            if (!data.success)
            {
                setConversationsError(data.message);
                return;
            }
            setConversations(data.conversations);
            conversationsRef.current = data.conversations;
            setConversationsError('');
        }
        catch
        {
            setConversationsError('טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.');
        }
        finally
        {
            setConversationsLoading(false);
        }
    }

    async function loadPeerName(peerId: string): Promise<void>
    {
        const known = conversationsRef.current.find((c) => c.peer_id === peerId)?.peer_name;
        if (known)
        {
            setPeerName(known);
            return;
        }

        try
        {
            const data = await usersApi.getPeerProfile(peerId);
            setPeerName(data.success ? (data.name || 'משתמש/ת') : 'משתמש/ת');
        }
        catch
        {
            setPeerName('משתמש/ת');
        }
    }

    async function loadMessages(peerId: string): Promise<void>
    {
        setMessagesLoading(true);
        try
        {
            const data = await chatApi.getMessages(peerId, { limit: PAGE_SIZE });
            if (!data.success)
            {
                setMessagesError(data.message);
                return;
            }
            setMessages([...data.messages].reverse());
            setHasOlder(data.messages.length === PAGE_SIZE);
            chatApi.markRead(peerId).catch(() => {});
            requestAnimationFrame(scrollToBottom);
        }
        catch
        {
            setMessagesError('טעינת השיחה נכשלה. אנא נסה/י שוב.');
        }
        finally
        {
            setMessagesLoading(false);
        }
    }

    async function loadOlderMessages(): Promise<void>
    {
        const peerId = peer_id;
        const oldest = messages[0];
        if (!peerId || !oldest || loadingOlder || !hasOlder)
        {
            return;
        }

        olderScrollHeightRef.current = messageListRef.current?.scrollHeight ?? null;
        setLoadingOlder(true);
        try
        {
            const data = await chatApi.getMessages(peerId, { before: oldest.message_id, limit: PAGE_SIZE });
            if (!data.success)
            {
                setMessagesError(data.message);
                return;
            }
            setMessages((prev) => [...[...data.messages].reverse(), ...prev]);
            setHasOlder(data.messages.length === PAGE_SIZE);
        }
        catch
        {
            setMessagesError('שגיאה בטעינת הודעות ישנות');
        }
        finally
        {
            setLoadingOlder(false);
        }
    }

    // Keep the viewport anchored on the same message after prepending an
    // older page, instead of letting it jump around underneath the reader.
    useEffect(() =>
    {
        const el = messageListRef.current;
        const prevHeight = olderScrollHeightRef.current;
        if (el && prevHeight != null)
        {
            el.scrollTop += el.scrollHeight - prevHeight;
            olderScrollHeightRef.current = null;
        }
    }, [messages]);

    function scrollToBottom(): void
    {
        const el = messageListRef.current;
        if (el)
        {
            el.scrollTop = el.scrollHeight;
        }
    }

    async function handleSend(): Promise<void>
    {
        const content = composerText.trim();
        if (!content || !peer_id || sending)
        {
            return;
        }

        setComposerText('');
        const tempId = `tmp-${Date.now()}`;
        const optimistic: Message = {
            message_id: tempId,
            sender_id:  user?.user_id ?? '',
            content,
            msg_type:   'TEXT',
            created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, optimistic]);
        requestAnimationFrame(scrollToBottom);

        const sentOverSocket = socketRef.current?.send(JSON.stringify({ peer_id, content, msg_type: 'TEXT' }));

        if (sentOverSocket)
        {
            pendingSendIdsRef.current.push(tempId);
            loadConversations(false);
            return;
        }

        setSending(true);
        try
        {
            const data = await chatApi.sendMessage(peer_id, content, 'TEXT');
            if (!data.success)
            {
                setMessages((prev) => prev.filter((m) => m.message_id !== tempId));
                setMessagesError(data.message);
                return;
            }
            const sent: Message = {
                message_id: data.message_id,
                sender_id:  data.sender_id,
                content:    data.content,
                msg_type:   data.msg_type,
                created_at: data.created_at,
            };
            setMessages((prev) => prev.map((m) => (m.message_id === tempId ? sent : m)));
            loadConversations(false);
        }
        catch
        {
            setMessages((prev) => prev.filter((m) => m.message_id !== tempId));
            setMessagesError('שליחת ההודעה נכשלה. נסה/י שנית.');
        }
        finally
        {
            setSending(false);
        }
    }

    return (
        <AppShell>
            <div className="h-full flex">
                <div className="w-80 shrink-0 border-e border-black/10 flex flex-col h-full bg-surface">
                    <h1 className="text-lg font-bold text-secondary px-5 py-4 border-b border-black/5">הודעות</h1>

                    <div className="flex-1 overflow-y-auto">
                        {conversationsLoading && (
                            <p className="text-secondary opacity-60 text-center py-6">טוען...</p>
                        )}

                        {conversationsError && (
                            <p className="text-danger text-sm text-center py-6 px-4">{conversationsError}</p>
                        )}

                        {!conversationsLoading && !conversationsError && conversations.length === 0 && (
                            <p className="text-secondary opacity-60 text-center py-6 px-4">
                                עדיין אין שיחות. התחילו שיחה ממסך הגילוי 🙂
                            </p>
                        )}

                        {conversations.map((conv) => (
                            <button
                                key={conv.peer_id}
                                type="button"
                                onClick={() => navigate(PAGE_ROUTES.chat.replace(':peer_id', conv.peer_id))}
                                className={`w-full text-right px-5 py-3 border-b border-black/5 hover:bg-black/5
                                            transition-colors ${conv.peer_id === peer_id ? 'bg-black/5' : ''}`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="font-semibold text-secondary truncate">
                                        {conv.peer_name || 'משתמש/ת'}
                                    </span>
                                    <span className="text-xs text-secondary opacity-50 shrink-0">
                                        {formatConversationTime(conv.last_created_at)}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between gap-2 mt-1">
                                    <span className="text-sm text-secondary opacity-60 truncate">
                                        {buildPreview(conv, user?.user_id ?? '')}
                                    </span>
                                    {conv.unread_count > 0 && (
                                        <span className="shrink-0 min-w-5 h-5 px-1.5 rounded-full bg-primary
                                                          text-white text-xs flex items-center justify-center">
                                            {conv.unread_count}
                                        </span>
                                    )}
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex-1 flex flex-col h-full min-w-0">
                    {!peer_id && (
                        <div className="flex-1 flex items-center justify-center">
                            <p className="text-white/60">בחרו שיחה מהרשימה כדי להתחיל</p>
                        </div>
                    )}

                    {peer_id && (
                        <>
                            <div className="px-6 py-4 border-b border-black/10 bg-surface">
                                <h2 className="font-bold text-secondary">{peerName || 'משתמש/ת'}</h2>
                            </div>

                            <div ref={messageListRef} className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-1">
                                {hasOlder && !messagesLoading && messages.length > 0 && (
                                    <button
                                        type="button"
                                        onClick={loadOlderMessages}
                                        disabled={loadingOlder}
                                        className="self-center text-sm text-white/60 hover:text-white
                                                   disabled:opacity-50 mb-3"
                                    >
                                        {loadingOlder ? 'טוען...' : 'טען הודעות ישנות'}
                                    </button>
                                )}

                                {messagesLoading && (
                                    <p className="text-white/60 text-center py-6">טוען...</p>
                                )}

                                {messagesError && (
                                    <p className="text-danger text-sm text-center py-2">{messagesError}</p>
                                )}

                                {messages.map((msg) => (
                                    <ChatBubble
                                        key={msg.message_id}
                                        content={msg.content}
                                        created_at={msg.created_at}
                                        isSelf={msg.sender_id === user?.user_id}
                                    />
                                ))}
                            </div>

                            <div className="px-6 py-4 border-t border-black/10 bg-surface flex items-center gap-3">
                                <input
                                    type="text"
                                    value={composerText}
                                    onChange={(e) => setComposerText(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
                                    placeholder="הקלידו הודעה…"
                                    className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-base
                                               text-right focus:outline-none focus:border-primary"
                                />
                                <button
                                    type="button"
                                    onClick={handleSend}
                                    disabled={sending || !composerText.trim()}
                                    className="px-6 py-3 rounded-card bg-primary text-white font-semibold
                                               disabled:opacity-50"
                                >
                                    {sending ? '...' : 'שלח'}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </AppShell>
    );
}
